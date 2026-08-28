# NSS ERP — Programmes & Events Business Rules

**Document ID:** SOL-MOD21-004  
**Version:** 0.1.0  
**Status:** DRAFT — BUSINESS RULES  
**Parent Documents:**
- SOL-EVT-001 — Programme & Event Domain Model
- SOL-EVT-002 — Event Entity Reconciliation
- SOL-MOD21-002 — Programmes & Events Logical ERD

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules for the proposed common
Programme & Event architecture.

The purpose is to establish the behavioral rules that govern:

- Programme Types
- Event Instances
- Organizers
- Event Locations
- Event Sessions
- Event recurrence
- Event publication
- Event cancellation
- Event rescheduling
- Event completion
- Participation
- Attendance integration
- Financial integration
- UPBS integration
- Kishor integration
- Sevak integration
- Authorization
- Notifications
- Audit and historical preservation

This document is the behavioral specification preceding the lifecycle and
physical database-design phases.

---

# 2. Rule Classification

Each rule is classified as one of:

| Classification | Meaning |
|---|---|
| **ERP-FROZEN** | Project-level ERP design decision already established |
| **DOMAIN-FROZEN** | Existing module rule that must be preserved |
| **CROSS-MODULE** | Rule requiring coordination between modules |
| **CONFIGURATION** | Behavior controlled by programme configuration |
| **PENDING** | Requires a future design decision |

No `PENDING` rule shall be treated as a frozen implementation rule.

---

# 3. Core Terminology

The following terminology is mandatory.

## 3.1 Programme Type

A reusable definition/configuration of a programme.

Examples:

```text
KISHOR_PUJA
JANMOUTSABA
SARADIYA_ALOCHANA_CHAKRA
UPBS
RASOUTSABA
```

## 3.2 Event Instance

One actual occurrence of a Programme Type.

Example:

```text
Programme Type:
    UPBS

Event:
    UPBS 2027
```

## 3.3 Organizer

An Organization responsible for organizing an Event.

## 3.4 Event Location

The physical/geographic location where an Event occurs.

## 3.5 Event Session

A logical segment/session within an Event.

Example:

```text
UPBS 2027
    ├── ADHIBASA
    ├── DAY_1
    ├── DAY_2
    └── DAY_3
```

---

# 4. BR-001 — Programme Type Is Distinct from Event

**Classification:** ERP-FROZEN

A Programme Type shall represent the reusable programme definition.

An Event shall represent one actual occurrence.

Therefore:

```text
Programme Type
      │
      ├── Event 2027
      ├── Event 2028
      └── Event 2029
```

An Event shall not be reused as the occurrence for multiple independent
years.

---

# 5. BR-002 — Event Belongs to a Programme Type

**Classification:** ERP-FROZEN

Every Event Instance shall belong to one Programme Type.

A Programme Type may have multiple Event Instances.

```text
PROGRAMME_TYPE 1 ───── N EVENT
```

---

# 6. BR-003 — Initial Programme Types

**Classification:** ERP-FROZEN

The current project configuration identifies the following Programme
Types:

1. KISHOR_PUJA
2. JANMOUTSABA
3. SARADIYA_ALOCHANA_CHAKRA
4. UPBS
5. RASOUTSABA

The existence of these Programme Types does not imply that all future
programmes must follow identical operational rules.

---

# 7. BR-004 — Default Organizer

**Classification:** ERP-FROZEN

The current default organizer configuration is:

| Programme Type           | Default Organizer       |
| ------------------------ | ----------------------- |
| KISHOR_PUJA              | Kendra                  |
| JANMOUTSABA              | Kendra                  |
| SARADIYA_ALOCHANA_CHAKRA | Kendra                  |
| UPBS                     | Kendra                  |
| RASOUTSABA               | Ekamra Saraswata Sangha |

The organizer is an Organization.

---

# 8. BR-005 — Organizer Is an Organization

**Classification:** ERP-FROZEN

An Event organizer shall reference an Organization.

The Programme & Event domain shall not create a separate organizer-master
concept that duplicates Organization.

```text
EVENT
   │
   └── organizer
          ↓
      ORGANIZATION
```

---

# 9. BR-006 — Organizer Is Not Event Location

**Classification:** ERP-FROZEN

Organizer and Event Location shall remain separate concepts.

Example:

```text
Organizer:
    Kendra

Location:
    Physical venue/address
```

An organization may be associated with the location, but the two
relationships shall not be conflated.

---

# 10. BR-007 — Organization Types Are Not Event Locations

**Classification:** ERP-FROZEN

The following are Organization concepts:

* Kendra
* Anchalika
* Zilla
* Sakha
* Patha Chakra

They shall not be represented as generic Event Location Types.

---

# 11. BR-008 — Patha Chakra Is an Organization

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

Patha Chakra is a permanent Organization.

NSS may have multiple Patha Chakras.

Patha Chakra shall therefore remain under the Organization domain.

---

# 12. BR-009 — Patha Chakra Transformation

**Classification:** CROSS-MODULE / PENDING

A Patha Chakra may in future be transformed into a Sakha Sangha through
an approved organizational process.

Conceptually:

```text
PATHA_CHAKRA
      ↓
approved Organization lifecycle transition
      ↓
SAKHA
```

The Event domain shall not implement this transformation.

The exact Organization lifecycle, approval and historical representation
remain owned by the Organization Module.

---

# 13. BR-010 — Event Location Is Physical/Geographic

**Classification:** ERP-FROZEN

Event Location shall represent the physical/geographic place where an
Event occurs.

It shall not represent organizational identity.

---

# 14. BR-011 — Programme Type Does Not Automatically Create an Event

**Classification:** ERP-FROZEN

The existence of a Programme Type shall not automatically create Event
Instances unless a future programme-specific configuration explicitly
supports such behavior.

The common Event framework shall not impose automatic event generation
on all programmes.

---

# 15. BR-012 — Annual Recurrence Is Programme Configuration

**Classification:** CONFIGURATION

A Programme Type may be configured as recurring annually.

Annual recurrence shall create separate Event Instances.

```text
UPBS
 ├── UPBS 2027
 ├── UPBS 2028
 └── UPBS 2029
```

Automatic generation mechanics remain PENDING.

---

# 16. BR-013 — Financial Year Is Independent of Calendar Year

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

Financial activity associated with an Event shall follow the Finance
Module's Financial Year.

Financial Year:

```text
01 April YYYY
      ↓
31 March YYYY+1
```

The Event's calendar date shall not redefine the Financial Year.

---

# 17. BR-014 — Event May Have Financial Scope

**Classification:** CROSS-MODULE

An Event may be associated with a Financial Scope where event-specific
financial management is required.

Example:

```text
UPBS 2027
    ↓
UPBS Financial Scope
```

Finance remains the owner of the Financial Scope and all financial
records.

---

# 18. BR-015 — Event Does Not Own Financial Transactions

**Classification:** CROSS-MODULE

The Programme & Event domain shall not own:

* transactions;
* receipts;
* payments;
* funds;
* transfers;
* financial-year records.

Those remain Finance-owned.

---

# 19. BR-016 — Multiple Financial Scopes May Exist for an Organization

**Classification:** DOMAIN-FROZEN

The Finance architecture distinguishes Financial Scope from
Organization.

Therefore an Organization may participate in multiple Financial Scopes
where permitted by Finance rules.

The Event domain shall not assume:

```text
One Organization = One Financial Scope
```

---

# 20. BR-017 — Event Sessions Are Optional

**Classification:** ERP-FROZEN

An Event may have zero, one, or multiple Event Sessions depending on the
Programme Type.

The system shall not require artificial sessions for programmes that do
not use them.

---

# 21. BR-018 — UPBS Sessions

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

UPBS currently uses the following session concepts:

* ADHIBASA
* DAY_1
* DAY_2
* DAY_3

The common Event model may represent these as Event Sessions.

UPBS-specific rules remain UPBS-owned.

---

# 22. BR-019 — Domain-Specific Extensions

**Classification:** ERP-FROZEN

The common Event model shall provide common Event identity and shared
behavior without absorbing domain-specific business rules.

Conceptually:

```text
EVENT
 ├── UPBS extension
 ├── Kishor extension
 └── Sevak extension
```

---

# 23. BR-020 — UPBS-Specific Entities Remain UPBS-Owned

**Classification:** DOMAIN-FROZEN

The following remain UPBS-domain concepts:

* UPBS Registration
* Delegate Card
* Prasad Patra
* Accommodation
* Camp
* Guest Reference

The common Event entity shall not absorb these concepts.

---

# 24. BR-021 — UPBS Event Integration

**Classification:** CROSS-MODULE / PENDING

The existing UPBS event identity shall eventually be reconciled with the
common Event entity.

Possible outcomes include:

1. existing UPBS event becomes an extension;
2. existing UPBS event references the common Event;
3. another approved mapping.

No migration strategy is frozen by this document.

---

# 25. BR-022 — Kishor Event Integration

**Classification:** CROSS-MODULE / PENDING

The existing Kishor event identity shall eventually be reconciled with
the common Event entity.

Kishor-specific participation rules remain Kishor-owned.

No migration strategy is frozen.

---

# 26. BR-023 — Sevak Event Types Remain Distinct

**Classification:** DOMAIN-FROZEN

The existing Sevak design identifies distinct event types including:

```text
SAKHA_SEVAK_SANGHA_SESSION
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

Their distinct business behavior shall not be erased by the common Event
model.

---

# 27. BR-024 — Sevak Event Creation

**Classification:** DOMAIN-FROZEN

Sevak event creation follows its existing domain rules.

Existing rules include:

* manual event creation;
* configurable frequency;
* host Sakha;
* event lifecycle;
* publication;
* cancellation;
* rescheduling;
* attendance;
* reconciliation.

The common Event framework shall not override these rules without an
explicit approved change.

---

# 28. BR-025 — Sevak Host Sakha

**Classification:** DOMAIN-FROZEN

A Sevak event requires a registered Sakha as host according to the
existing Sevak business rules.

This is a Sevak-specific rule.

It shall not become a universal requirement for all Event Types.

---

# 29. BR-026 — Sevak Location Rule

**Classification:** DOMAIN-FROZEN

For Sevak events, the existing rules use the host Sakha's registered
location and preserve the location as a historical snapshot.

This behavior remains Sevak-owned unless explicitly promoted to a common
Event rule.

---

# 30. BR-027 — Organizer and Host Are Distinct Concepts

**Classification:** ERP-FROZEN / DOMAIN-FROZEN

The common model shall permit Organizer and Host to be distinct
relationships.

For example:

```text
EVENT
 ├── organizer → Organization
 │
 └── Sevak host → Sakha
```

The Sevak host rule shall not redefine the universal organizer model.

---

# 31. BR-028 — Eligibility Is Distinct from Attendance

**Classification:** CROSS-MODULE

The following concepts shall remain distinct:

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

---

# 32. BR-029 — Attendance Is Attendance-Owned

**Classification:** CROSS-MODULE

Actual attendance shall remain owned by the Attendance Module.

The Programme & Event domain shall reference or invoke Attendance
functionality rather than creating a separate attendance mechanism.

---

# 33. BR-030 — Event Participation Does Not Change Organization

**Classification:** CROSS-MODULE

Attending an Event organized or hosted by another Organization shall not
automatically change:

* membership;
* organizational affiliation;
* Sakha;
* organizational status.

Conceptually:

```text
Attend Event
    ≠
Change Organization
```

---

# 34. BR-031 — Cross-Organization Participation

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

A person may participate in an Event outside their normal organizational
context where the relevant Programme rules permit it.

Such participation shall not imply organizational transfer.

---

# 35. BR-032 — Event Visibility

**Classification:** CROSS-MODULE / PENDING

Event visibility shall be governed by programme-specific participation
and authorization rules.

The common model may provide a publication/visibility state, but the
exact visibility matrix remains PENDING.

---

# 36. BR-033 — Event Publication

**Classification:** ERP-FROZEN / DOMAIN-FROZEN

An Event may progress from an internal draft state to a published state.

Publication shall make the Event available according to the applicable
visibility and authorization rules.

The exact universal status vocabulary remains PENDING.

---

# 37. BR-034 — Event Cancellation

**Classification:** CROSS-MODULE

An Event may be cancelled according to the applicable programme rules.

Cancellation shall not physically delete the Event.

Historical identity shall be retained.

---

# 38. BR-035 — Event Rescheduling

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

Where rescheduling is permitted, the system shall preserve historical
Event identity and the relevant scheduling history.

The existing Sevak rules require preservation of:

* original Event identity;
* historical scheduling;
* existing attendance;
* relevant intention information.

These principles are candidates for common Event behavior.

---

# 39. BR-036 — Rescheduling Does Not Create Organizational Transfer

**Classification:** CROSS-MODULE

Rescheduling an Event shall not alter the organizational affiliation of
participants.

---

# 40. BR-037 — Event Completion

**Classification:** CROSS-MODULE

An Event may be marked completed after the applicable programme
activities and reconciliation have been completed.

Completion shall preserve historical Event information.

---

# 41. BR-038 — Event Reconciliation

**Classification:** CROSS-MODULE / PENDING

Some programmes require post-event reconciliation.

The existing Sevak model includes reconciliation for:

* attendance;
* actual participation;
* legitimate attendee corrections;
* post-event review.

Whether a universal Event Reconciliation entity is required remains
PENDING.

---

# 42. BR-039 — Post-Completion Editing

**Classification:** CROSS-MODULE

Completed historical Events shall not be freely modified.

Any correction after completion shall follow the applicable centralized
approval and audit mechanisms.

---

# 43. BR-040 — Historical Preservation

**Classification:** ERP-FROZEN

Event history shall be preserved.

Historical records shall not be physically deleted merely because an
Event is cancelled, rescheduled or completed.

---

# 44. BR-041 — No Physical Deletion

**Classification:** ERP-FROZEN

The common Event architecture shall follow the project's established
soft-delete/historical preservation standards.

Physical deletion of historical Event records is prohibited unless an
explicit governance-approved exception exists.

---

# 45. BR-042 — Event Audit

**Classification:** CROSS-MODULE

Event creation, modification, cancellation, rescheduling, publication
and completion shall be auditable.

The Event domain consumes the centralized Audit architecture.

It shall not create an independent audit framework.

---

# 46. BR-043 — Authorization Uses Common RBAC

**Classification:** CROSS-MODULE

Event authorization shall use the existing Administration/RBAC
framework.

The Event domain shall not create:

* independent roles;
* independent permissions;
* independent user-role mappings.

---

# 47. BR-044 — Organizational Scope

**Classification:** CROSS-MODULE

Event authorization may depend on organizational scope.

The exact scope matrix shall use the existing Administration model.

Geographic hierarchy and organizational authorization scope shall not be
treated as identical concepts.

---

# 48. BR-045 — Notification Integration

**Classification:** CROSS-MODULE

Event lifecycle changes may trigger notifications.

Examples include:

* publication;
* cancellation;
* rescheduling;
* relevant participation changes.

Notification remains shared infrastructure.

The Event domain shall not create duplicate notification mechanisms.

---

# 49. BR-046 — Notification Is Not Event Ownership

**Classification:** ERP-FROZEN

Notification generation does not transfer ownership of Event business
rules to a Notification capability.

The Event domain remains responsible for the Event state change.

---

# 50. BR-047 — Programme Configuration

**Classification:** CONFIGURATION

A Programme Type may contain configuration such as:

* programme code;
* programme name;
* default organizer;
* recurrence characteristics;
* active/inactive state;
* programme classification;
* default session configuration.

Exact physical representation remains PENDING.

---

# 51. BR-048 — Programme Configuration Shall Not Hard-Code Business Rules

**Classification:** ERP-FROZEN

Configuration shall not be used to bypass mandatory domain business
rules.

For example, configuring a programme as recurring shall not automatically
override its domain-specific creation, eligibility or authorization
rules.

---

# 52. BR-049 — Annual Programmes

**Classification:** CONFIGURATION

The following programmes are currently treated as annual recurring
programme types:

```text
KISHOR_PUJA
JANMOUTSABA
SARADIYA_ALOCHANA_CHAKRA
UPBS
RASOUTSABA
```

Each annual occurrence shall have its own Event Instance.

---

# 53. BR-050 — Annual Event Generation

**Classification:** PENDING

The system may eventually support automatic generation of annual Event
Instances.

However, automatic generation is not yet a universal frozen rule.

Existing Sevak rules explicitly use manual Event creation.

---

# 54. BR-051 — Programme-Specific Recurrence

**Classification:** DOMAIN-FROZEN / CONFIGURATION

Different Programme Types may have different recurrence models.

The common Event architecture shall not require every Programme Type to
be annual.

---

# 55. BR-052 — Event Location History

**Classification:** CROSS-MODULE / PENDING

Where an Event's location changes or an Organization's location changes,
the system may need to preserve the location applicable at the time of
the Event.

The Sevak module already requires historical location capture.

Whether this becomes a universal Event rule remains PENDING.

---

# 56. BR-053 — Event Location Does Not Change Organization

**Classification:** ERP-FROZEN

Holding an Event at a particular location shall not automatically change
the Event organizer or the organizational identity of participants.

---

# 57. BR-054 — Event Session Ownership

**Classification:** CROSS-MODULE / PENDING

Event Sessions may be common infrastructure where multiple programmes
use the same session concept.

Where a programme has genuinely unique session semantics, those rules may
remain domain-specific.

---

# 58. BR-055 — UPBS Session Mapping

**Classification:** DOMAIN-FROZEN / CROSS-MODULE

UPBS session concepts may be represented using the common Event Session
model:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

The UPBS Module remains authoritative for the meaning and operational
rules of those sessions.

---

# 59. BR-056 — Event Extension Ownership

**Classification:** ERP-FROZEN

A domain-specific Event extension shall be owned by the corresponding
domain module.

Examples:

```text
UPBS → UPBS
Kishor → Kishor
Sevak → Sevak
```

The common Event entity shall not absorb domain-specific extension data.

---

# 60. BR-057 — One Physical Table, One Owner

**Classification:** ERP-FROZEN

If the common Event entity becomes a physical table, exactly one module
shall own its DDL.

Other modules shall reference it.

Duplicate Event tables are prohibited.

---

# 61. BR-058 — Existing Event Tables Are Not Automatically Replaced

**Classification:** ERP-FROZEN

Existing module-specific Event tables shall not be deleted, renamed or
migrated merely because a common Event architecture has been proposed.

Migration requires an explicit approved design.

---

# 62. BR-059 — UPBS Migration Requires Explicit Approval

**Classification:** PENDING

Any migration from `upbs_event` to a common Event entity shall require:

* field mapping;
* PK/FK mapping;
* historical-data strategy;
* application migration strategy;
* backward-compatibility analysis;
* acceptance testing.

---

# 63. BR-060 — Kishor Migration Requires Explicit Approval

**Classification:** PENDING

Any migration of existing Kishor event structures requires the same
formal reconciliation and approval.

---

# 64. BR-061 — Sevak Migration Requires Explicit Approval

**Classification:** PENDING

Any migration of existing Sevak Event structures must preserve:

* host Sakha;
* location behavior;
* eligibility;
* intention;
* probable attendance;
* attendance;
* cancellation;
* rescheduling;
* reconciliation;
* historical records.

---

# 65. BR-062 — Finance Integration

**Classification:** CROSS-MODULE

The Event domain shall integrate with Finance through Financial Scope.

The Event domain shall not create finance-specific tables.

---

# 66. BR-063 — Event Finance Is Not Calendar-Year Based

**Classification:** CROSS-MODULE

Financial transactions associated with Events shall use the Finance
Module's Financial Year.

The Event's calendar year is not a Financial Year.

---

# 67. BR-064 — Event-Specific Financial Scope

**Classification:** CROSS-MODULE

A Programme/Event may have its own Financial Scope when financial
management is required.

Examples:

```text
UPBS 2027
Kishor Puja 2027
Janmoutsaba 2027
Rasoutsaba 2027
```

The exact Financial Scope cardinality remains governed by Finance.

---

# 68. BR-065 — Finance Scope Does Not Equal Organization

**Classification:** CROSS-MODULE

A Financial Scope shall not be treated as synonymous with an
Organization.

For example:

```text
Kendra
    ≠
Financial Scope
```

An Organization may have multiple Financial Scopes.

A Financial Scope may be associated with an Event.

---

# 69. BR-066 — Event Authorization

**Classification:** CROSS-MODULE

Actions such as:

* create;
* edit;
* publish;
* cancel;
* reschedule;
* complete;
* correct

shall be subject to the applicable RBAC and organizational-scope rules.

The exact permission matrix remains PENDING.

---

# 70. BR-067 — Governance Roles Are Not Application Roles

**Classification:** ERP-FROZEN / CROSS-MODULE

Statutory organizational positions shall not
automatically be treated as application roles.

Application authorization shall use the Administration/RBAC framework.

---

# 71. BR-068 — Event Creation Authority

**Classification:** PENDING

The exact set of roles permitted to create Event Instances shall be
defined through the Administration/RBAC and Programme/Event
authorization design.

Existing Sevak rules require specific creation authority.

This shall not automatically become the universal Event rule.

---

# 72. BR-069 — Event Publication Authority

**Classification:** PENDING

The exact roles permitted to publish an Event shall be defined by the
authorization matrix.

Publication shall not be implicitly granted to every Event creator.

---

# 73. BR-070 — Event Cancellation Authority

**Classification:** PENDING

The exact roles permitted to cancel an Event shall be defined by the
authorization matrix.

Cancellation must remain auditable.

---

# 74. BR-071 — Event Rescheduling Authority

**Classification:** PENDING

The exact roles permitted to reschedule an Event shall be defined by the
authorization matrix.

Rescheduling must preserve historical information.

---

# 75. BR-072 — Event Completion Authority

**Classification:** PENDING

The exact roles permitted to complete an Event shall be defined by the
authorization matrix.

Completion should occur only after applicable reconciliation.

---

# 76. BR-073 — Event Visibility and Authorization

**Classification:** CROSS-MODULE / PENDING

Event visibility may depend on:

* publication state;
* user role;
* organizational scope;
* programme eligibility;
* Event-specific rules.

These dimensions must not be collapsed into a single generic concept.

---

# 77. BR-074 — Programme-Specific Eligibility

**Classification:** DOMAIN-FROZEN

A programme may define eligibility rules that differ from another
programme.

The common Event model shall not impose universal eligibility criteria.

---

# 78. BR-075 — Event Participation Does Not Imply Membership

**Classification:** CROSS-MODULE

Participation in an Event shall not automatically create:

* membership;
* probationary membership;
* organizational affiliation;
* Sevak status;
* Kishor status;
* other domain identity.

Domain-specific onboarding rules remain authoritative.

---

# 79. BR-076 — Event Does Not Create Person Identity

**Classification:** CROSS-MODULE

The Event domain shall consume Person identity.

It shall not create duplicate Person records.

---

# 80. BR-077 — Event Does Not Create Organization Identity

**Classification:** CROSS-MODULE

The Event domain shall consume Organization identity.

It shall not create duplicate Organization records.

---

# 81. BR-078 — Event Does Not Create Authentication Identity

**Classification:** CROSS-MODULE

The Event domain shall consume Authentication and Administration
services.

It shall not create:

* users;
* passwords;
* roles;
* permissions.

---

# 82. BR-079 — Event Does Not Create Independent Audit Infrastructure

**Classification:** CROSS-MODULE

Event changes shall use the centralized Audit architecture.

No independent Event audit framework shall be created.

---

# 83. BR-080 — Event Historical Integrity

**Classification:** ERP-FROZEN

The following historical information shall remain recoverable where
applicable:

* Event identity;
* Event schedule;
* organizer;
* location;
* publication state;
* cancellation;
* rescheduling;
* completion;
* participation;
* attendance;
* financial linkage.

Exact physical implementation remains subject to table design.

---

# 84. BR-081 — Event Status Values

**Classification:** PENDING

A common Event status vocabulary is not yet frozen.

The following are candidate conceptual states:

```text
DRAFT
PUBLISHED
ACTIVE
COMPLETED
CANCELLED
```

Additional states such as RESCHEDULED may be represented as lifecycle
transitions or historical events rather than persistent status values.

The final representation shall be determined in the lifecycle document.

---

# 85. BR-082 — Event Lifecycle Must Preserve History

**Classification:** ERP-FROZEN

Lifecycle transitions shall not destroy the historical Event identity.

Example:

```text
DRAFT
  ↓
PUBLISHED
  ↓
RESCHEDULED
  ↓
ACTIVE
  ↓
COMPLETED
```

The Event history shall remain auditable.

---

# 86. BR-083 — Event Rescheduling History

**Classification:** DOMAIN-FROZEN / PENDING

Sevak already requires preservation of historical scheduling information.

Whether a common Event Rescheduling History entity is required remains
PENDING.

---

# 87. BR-084 — Event Reconciliation History

**Classification:** DOMAIN-FROZEN / PENDING

Sevak already requires post-event reconciliation.

Whether the common architecture requires a universal reconciliation
history entity remains PENDING.

---

# 88. BR-085 — No Universal Sevak Rules

**Classification:** ERP-FROZEN

The following Sevak-specific concepts shall not automatically become
requirements for all Event Types:

* host Sakha;
* Sevak eligibility;
* intention;
* probable attendance;
* reactivation review;
* Sevak-specific notifications;
* Sevak-specific reconciliation.

---

# 89. BR-086 — No Universal UPBS Rules

**Classification:** ERP-FROZEN

The following UPBS-specific concepts shall not automatically become
requirements for all Event Types:

* registration;
* delegate card;
* Prasad Patra;
* accommodation;
* camp;
* guest reference.

---

# 90. BR-087 — Common Event Is a Shared Foundation

**Classification:** ERP-FROZEN

The proposed common Event architecture exists to provide shared
identity and shared infrastructure.

It is not intended to replace the individual programme domains.

---

# 91. BR-088 — Common Programme/Event Module Ownership

**Classification:** PENDING

The project has not yet formally frozen whether Programme & Events will
become a standalone module.

The decision shall follow acceptance of:

* Domain Model;
* Reconciliation;
* Logical ERD;
* Business Rules;
* Lifecycle;
* Table Design.

---

# 92. BR-089 — Event Table Ownership

**Classification:** PENDING

If a physical common Event table is approved, its owning module must be
explicitly designated.

No module may independently create a duplicate common Event table.

---

# 93. BR-090 — Event Location Ownership

**Classification:** PENDING

The final ownership and physical representation of Event Location remain
OPEN.

The logical distinction from Organization is already established.

---

# 94. BR-091 — Programme Type Physical Representation

**Classification:** PENDING

The project has not yet frozen whether Programme Type shall be:

1. a dedicated physical entity;
2. master data;
3. another approved configuration mechanism.

The final decision belongs to the physical database-design phase.

---

# 95. BR-092 — Event Session Physical Representation

**Classification:** PENDING

The logical Event Session entity is supported by UPBS.

Whether it becomes a common physical entity or remains programme-specific
shall be determined during table design.

---

# 96. BR-093 — Event Location Snapshot

**Classification:** PENDING

The system may need to preserve the location applicable at the time an
Event occurred.

Sevak already requires historical location capture.

A universal snapshot strategy remains PENDING.

---

# 97. BR-094 — Programme Type Deactivation

**Classification:** CONFIGURATION

A Programme Type that is no longer active shall not automatically erase
its historical Event Instances.

Historical Events remain preserved.

---

# 98. BR-095 — Event Historical Preservation After Programme Deactivation

**Classification:** ERP-FROZEN

Deactivating a Programme Type shall not delete historical Events created
from that Programme Type.

---

# 99. BR-096 — Event Data Ownership

**Classification:** ERP-FROZEN

The common Event entity, if physically implemented, shall contain only
information genuinely common to Events.

Domain-specific information remains in the owning domain.

---

# 100. BR-097 — No Generic Catch-All Event Attributes

**Classification:** ERP-FROZEN

The common Event entity shall not become a generic catch-all container
using unrestricted attributes merely to avoid domain-specific modeling.

Domain-specific requirements shall be represented through explicit
domain extensions where justified.

---

# 101. BR-098 — Event Programme Classification

**Classification:** PENDING

Programme classification may be used to distinguish:

* annual programmes;
* special programmes;
* domain programmes;
* future programme categories.

The exact classification vocabulary remains OPEN.

---

# 102. BR-099 — Special Events

**Classification:** CROSS-MODULE

The common Event architecture shall support special/one-off Events in
addition to recurring programmes.

A special Event does not need to belong to an annual Programme Type if
the final Programme Type design explicitly permits this.

The exact representation remains PENDING.

---

# 103. BR-100 — Special Event Finance

**Classification:** CROSS-MODULE

A special Event may have its own Financial Scope where required.

Finance shall continue to use the Financial Year model.

---

# 104. BR-101 — Future Programmes

**Classification:** ERP-FROZEN

The common architecture shall allow future NSS programmes to be added
without requiring a new database architecture for every programme.

A new programme may consume the common Event framework while retaining
domain-specific extension entities where justified.

---

# 105. BR-102 — Future Programme Does Not Automatically Become a New Module

**Classification:** PENDING

The existence of a new Programme Type does not automatically justify a
new ERP module.

Module creation shall depend on domain complexity, ownership,
business rules and physical data requirements.

---

# 106. BR-103 — Event Type vs Programme Type

**Classification:** ERP-FROZEN

Programme Type and Event Type shall not be treated as interchangeable.

A Programme Type defines the broader programme.

An Event is an occurrence.

An Event Type, if required, may classify an Event within a Programme.

The exact Event Type model remains PENDING.

---

# 107. BR-104 — Patha Chakra Is Not Programme Type

**Classification:** ERP-FROZEN

Patha Chakra is an Organization Type.

It shall not be represented as a Programme Type or Event Type.

---

# 108. BR-105 — Kendra Is Not Event Location Type

**Classification:** ERP-FROZEN

Kendra is an Organization concept.

It shall not be represented as an Event Location Type.

---

# 109. BR-106 — Sakha Is Not Event Location Type

**Classification:** ERP-FROZEN

Sakha is an Organization concept.

It shall not be represented as an Event Location Type.

---

# 110. BR-107 — Event Organizer May Differ by Programme

**Classification:** CONFIGURATION

Different Programme Types may have different default organizers.

Current configuration includes:

```text
Kendra
Ekamra Saraswata Sangha
```

The common architecture shall not hard-code Kendra as the universal
organizer.

---

# 111. BR-108 — Event Location May Differ by Occurrence

**Classification:** ERP-FROZEN

Two Events of the same Programme Type may occur at different physical
locations.

Example:

```text
UPBS 2027 → Location A
UPBS 2028 → Location B
```

Therefore Event Location belongs conceptually to the Event occurrence,
not solely to Programme Type.

---

# 112. BR-109 — Organizer May Differ by Occurrence

**Classification:** PENDING

Whether the organizer may be overridden for an individual Event Instance
remains PENDING.

If permitted, the override must be explicitly recorded and auditable.

---

# 113. BR-110 — Event Session Order

**Classification:** CONFIGURATION / PENDING

Where Event Sessions are used, the Programme may define their logical
sequence.

UPBS provides:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

The exact universal session-ordering mechanism remains PENDING.

---

# 114. BR-111 — Event Session Does Not Become Independent Event

**Classification:** ERP-FROZEN

An Event Session is a segment of an Event.

It shall not automatically become a separate Event Instance.

Example:

```text
UPBS 2027
   └── DAY_1
```

DAY_1 remains part of UPBS 2027 unless a future domain rule explicitly
requires independent Event identity.

---

# 115. BR-112 — Event Date/Time

**Classification:** ERP-FROZEN

An Event occurrence shall have a date/time context.

The exact support for:

* single-day Events;
* multi-day Events;
* timed sessions;
* timezone;
* all-day events

shall be finalized in physical design.

---

# 116. BR-113 — Multi-Day Events

**Classification:** ERP-FROZEN

The common architecture shall support multi-day Events.

UPBS is an existing validation case.

The Event Instance remains one Event with multiple sessions or date/time
segments as appropriate.

---

# 117. BR-114 — Event Date Does Not Define Financial Year

**Classification:** CROSS-MODULE

An Event occurring near a financial-year boundary shall use Finance's
Financial Year determination for its financial transactions.

The Event domain shall not infer financial-year membership solely from
calendar-year naming.

---

# 118. BR-115 — Audit Columns

**Classification:** CROSS-MODULE

Physical Event tables shall follow the project's database audit-column
standards.

The exact audit FK targets shall follow the approved database design.

---

# 119. BR-116 — Soft Delete

**Classification:** ERP-FROZEN

Physical Event entities shall follow the project's soft-delete and
historical preservation standards.

No physical deletion of historical business Events shall be permitted
under normal operations.

---

# 120. BR-117 — Cross-Module Foreign Keys

**Classification:** ERP-FROZEN

When physical Event tables are designed, cross-module references shall
follow the project's common database standards.

The Event module shall reference:

* Organization;
* Person where explicitly required;
* Attendance;
* Finance;

rather than duplicating their identity structures.

---

# 121. BR-118 — API Is Deferred

**Classification:** ERP-FROZEN

API contracts shall be designed only after:

1. Business Rules;
2. Lifecycle;
3. Physical Table Design.

This follows the project's Database-First → API-First → UI sequence.

---

# 122. BR-119 — UI Is Deferred

**Classification:** ERP-FROZEN

UI behavior shall not be frozen until the underlying Event business rules,
lifecycle and API contracts are established.

---

# 123. BR-120 — No Physical DDL from This Document

**Classification:** ERP-FROZEN

This document does not authorize physical DDL.

The physical table design must be produced separately after lifecycle
decisions are complete.

---

# 124. Business Rule Summary

The common Programme & Event architecture therefore establishes:

```text
Programme Type
      │
      ▼
Event Instance
      │
      ├── Organizer → Organization
      │
      ├── Location → Physical/Geographic Location
      │
      ├── Sessions → optional
      │
      ├── Attendance → Attendance Module
      │
      ├── Financial Scope → Finance Module
      │
      └── Domain Extensions
              ├── UPBS
              ├── Kishor
              └── Sevak
```

The common layer provides shared Event infrastructure.

The domain modules retain their domain-specific rules.

---

# 125. Pending Decisions Summary

The following remain intentionally unresolved:

| #  | Decision                                  |
| -- | ----------------------------------------- |
| 1  | Physical Programme Type representation    |
| 2  | Physical Event ownership                  |
| 3  | Event Location representation             |
| 4  | Event Location snapshot strategy          |
| 5  | Event-level organizer override            |
| 6  | Universal Event status vocabulary         |
| 7  | Universal Event lifecycle                 |
| 8  | Universal Event reconciliation entity     |
| 9  | Event Session physical representation     |
| 10 | Common Event Type vocabulary              |
| 11 | Automatic annual Event generation         |
| 12 | Special Event representation              |
| 13 | UPBS migration/extension strategy         |
| 14 | Kishor migration/extension strategy       |
| 15 | Sevak migration/extension strategy        |
| 16 | Final Programme & Events module ownership |

---

# 126. Next Artifact

The next document shall be:

```text
PROGRAMMES_EVENTS_LIFECYCLE.md
```

The lifecycle document shall convert the approved behavioral concepts
into explicit:

* states;
* transitions;
* guards;
* actions;
* approvals;
* cancellation;
* rescheduling;
* completion;
* reconciliation;
* historical preservation.

It shall not introduce new business rules without identifying them as
PENDING.

---

# 127. Status

```text
DOCUMENT STATUS:
DRAFT — BUSINESS RULES

VERSION:
0.1.0

PROGRAMME TYPE:
LOGICALLY DEFINED

EVENT:
LOGICALLY DEFINED

ORGANIZER:
ORGANIZATION

EVENT LOCATION:
PHYSICAL / GEOGRAPHIC

EVENT SESSION:
OPTIONAL COMMON CONCEPT

ATTENDANCE:
SEPARATE DOMAIN

FINANCE:
SEPARATE DOMAIN

FINANCIAL YEAR:
01 APRIL – 31 MARCH

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
PROGRAMMES_EVENTS_LIFECYCLE.md
```

# End of Document
