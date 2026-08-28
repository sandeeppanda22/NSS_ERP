# NSS ERP — Kishor Puja Lifecycle

**Document ID:** SOL-KISH-003  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kishor Puja  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle of a Kishor participant within the NSS ERP.

The lifecycle covers:

- Person association
- Kishor identification
- First registration
- KH ID generation
- Sakha association
- Guardian assignment
- Annual Kishor Puja registration
- Event participation
- Repeated year-wise participation
- Membership consideration
- NSS Membership transition
- Historical preservation

Kishor Puja is an annual/event-based participation model.

It is not modeled as a permanent organizational unit like Kumari Sangha.

---

# 2. Fundamental Lifecycle Principle

The Kishor lifecycle consists of two different layers:

```text
Participant Lifecycle
        +
Annual Event Lifecycle
```

The participant identity is permanent.

The event participation is year-specific.

Therefore:

```text
KH ID
=
Permanent

Event Registration
=
Year/Event Specific
```

---

# 3. Person Foundation

The lifecycle begins with an existing Person record.

```text
PERSON
   ↓
KISHOR PARTICIPANT
```

The Kishor module does not create a duplicate Person identity.

---

# 4. Eligibility / Identification

An eligible boy may enter the Kishor Puja process.

The frozen participation model includes:

* Boys from NSS families
* Sons of NSS members
* Boys nominated by parents
* Boys nominated by Sangha

The exact detailed age boundary is not frozen in the current source and therefore is not hard-coded by this lifecycle document.

---

# 5. Entry Sources

Kishor registration may originate through:

```text
Family / Parent
        ↓
Nomination
        ↓
Kishor Registration
```

or:

```text
Sakha
        ↓
Nomination
        ↓
Kishor Registration
```

Both routes ultimately create/identify the same Kishor participant identity.

---

# 6. First Kishor Registration

The first registration establishes the participant's Kishor identity.

Conceptually:

```text
Eligible Person
      ↓
First Kishor Registration
      ↓
Kishor Participant
      ↓
KH ID
```

---

# 7. KH ID Generation

On first registration, the system generates a Kishor ID.

Example:

```text
KH000001
KH000002
KH000003
```

The KH ID is:

* Unique
* Permanent
* Never reused
* Retained across years

This is explicitly frozen in the project source.

---

# 8. KH ID Permanence

Once assigned:

```text
KH000123
```

remains the identity of that Kishor participant.

A later annual event does not generate another KH ID.

---

# 9. Re-registration Across Years

A participant may participate in multiple Kishor Puja years.

Example:

```text
KH000123

2026 Kishor Puja
2027 Kishor Puja
2028 Kishor Puja
```

All three years remain connected to:

```text
KH000123
```

The source explicitly freezes retention of participation history across years.

---

# 10. Sakha Association

Every Kishor registration must be associated with a Sakha.

This association is required for:

* Operational ownership
* Reporting
* Visibility
* Guardian assignment
* Sakha-level administration

The registration remains Sakha-associated even when the registration originated through a parent nomination.

---

# 11. Sakha Does Not Become Kishor Identity

The Sakha association does not replace the participant identity.

Therefore:

```text
Sakha
   ≠
KH ID
```

A change in organizational context does not create a new KH ID.

---

# 12. Guardian Requirement

Every Kishor participant must have an assigned Guardian.

This is a frozen rule.

The Guardian is:

```text
NSS Member
+
Member of Participant's Sakha
+
Assigned by Sakha
```

The Guardian is not necessarily the participant's parent.

---

# 13. Guardian Assignment

After Kishor participation is established:

```text
Kishor Participant
        ↓
Guardian Required
        ↓
Sakha Assigns Guardian
        ↓
NSS Member of Same Sakha
```

The assignment must be recorded.

---

# 14. Guardian Responsibilities

The assigned Guardian provides:

* Guidance
* Supervision
* Participation monitoring
* Communication with family
* Support during Kishor Puja
* Support during related activities

These responsibilities are part of the frozen Guardian Model.

---

# 15. Guardian Assignment History

Guardian assignment shall be historically traceable.

At minimum, the lifecycle must preserve:

```text
Guardian
Assigned Sakha
Assignment Date
```

The Sakha responsible for the assignment must also be identifiable.

---

# 16. Guardian Change

Where an authorized Sakha changes the Guardian:

```text
Old Guardian
      ↓
Historical Assignment
      ↓
New Guardian
```

The participant retains:

```text
Same Person
Same KH ID
```

A Guardian change does not create a new Kishor identity.

---

# 17. Annual Event Creation

A Kishor Puja event is created for a particular occurrence/year.

Example:

```text
Kishor Puja 2026
```

The event has its own identity and lifecycle.

---

# 18. Event Lifecycle

The event lifecycle is separate from the participant lifecycle.

Conceptually:

```text
EVENT CREATED
      ↓
EVENT AVAILABLE FOR REGISTRATION
      ↓
REGISTRATION
      ↓
EVENT PARTICIPATION
      ↓
EVENT COMPLETION
      ↓
HISTORICAL RECORD
```

The exact event status values are governed by the common Event framework where applicable.

---

# 19. Event Year

Each event is associated with its applicable year/financial year.

Example:

```text
2026
2027
2028
```

Year-specific event records support reporting and historical participation.

---

# 20. Event Registration

A Kishor participant registers for a specific Kishor Puja event.

```text
KH000123
      ↓
Kishor Puja 2026
      ↓
Event Registration
```

The registration is distinct from the permanent participant record.

---

# 21. Registration Ownership

Every registration must identify the relevant Sakha.

Conceptually:

```text
Kishor Participant
        ↓
Registered Under
        ↓
Sakha
```

This is frozen for operational ownership and reporting.

---

# 22. Registration Status

Registration status belongs to the annual event registration.

It must not be confused with the permanent Kishor identity.

Conceptually:

```text
Kishor Participant
=
Permanent Identity

Registration
=
Event-Specific State
```

---

# 23. Registration vs Participation

These are separate concepts:

```text
Registration
      ≠
Actual Participation
```

A registered Kishor may not ultimately participate.

Where attendance is required, the common Attendance framework remains authoritative.

---

# 24. Registration vs Attendance

The lifecycle shall not automatically interpret:

```text
Registered
```

as:

```text
Attended
```

Attendance is separately recorded.

---

# 25. Annual Participation

When the participant actually takes part in the event:

```text
Event Registration
      ↓
Participation
      ↓
Historical Event Record
```

The participation remains associated with the same KH ID.

---

# 26. Multiple Annual Participations

A single participant may have:

```text
KH000123

Registration 2026
Participation 2026

Registration 2027
Participation 2027

Registration 2028
Participation 2028
```

These records form the participant's Kishor participation history.

---

# 27. No New KH ID Per Year

The following is prohibited:

```text
2026 → KH000123
2027 → KH000456
```

for the same person.

The correct lifecycle is:

```text
2026 → KH000123
2027 → KH000123
2028 → KH000123
```

---

# 28. Cross-Sangha Participation

Participants may come from different Sanghas.

Participation in an event does not automatically change the participant's organizational affiliation.

Conceptually:

```text
Home Sakha
    ≠
Event Host
```

where applicable.

---

# 29. Host Organization

A Kishor event may be organized/hosted by an authorized NSS organization.

The event host is part of the event record.

The host organization does not automatically become the participant's Sakha.

---

# 30. Historical Sakha Context

Sakha information relevant to registration shall be retained so that historical reports remain accurate.

For example:

```text
KH000123

2026 → Sakha A
2027 → Sakha A
2028 → Sakha B
```

The system must not rewrite the 2026 record simply because the participant's current organizational association later changes.

---

# 31. Family Visibility

Family members may view Kishor information belonging to their own family.

The frozen Family Visibility rule includes:

* Participant details
* Registration details
* Activity history where applicable
* Training history where applicable
* Participation status
* Assigned Guardian
* Membership transition status

Family access is restricted to the family's own records.

---

# 32. Sakha Visibility

Sakha-authorized users may view Kishor registrations belonging to their own Sakha.

This includes:

* Total registrations
* Active registrations
* Year-wise registrations
* Participant list
* Guardian details
* Participation status

The source explicitly freezes Sakha-scoped visibility.

---

# 33. Kendra Visibility

Kendra-authorized users may view Kishor information across Sakhas.

This includes:

* All registrations
* All Sakhas
* Year-wise reports
* District/state-level reports where applicable
* Complete participant history

---

# 34. Guardian Visibility

The assigned Guardian may access authorized information for participants assigned to that Guardian, subject to common RBAC and privacy rules.

---

# 35. Event Completion

After the Kishor event is completed:

```text
Event
   ↓
Completed
   ↓
Historical Record
```

The event and its registration/participation history remain preserved.

---

# 36. Historical Preservation

The following must remain traceable:

```text
KH ID
First Registration
Sakha Association
Guardian Assignment
Annual Event Registrations
Annual Participation
Event History
Membership Transition
```

Historical records are not discarded merely because the participant's current state changes.

---

# 37. Membership Consideration

Long-term Kishor participants may be considered for NSS Membership.

The source explicitly states that long-term Kishor participants may be considered for Regular Membership without mandatory probation, based on their existing:

* NSS philosophy exposure
* Discipline
* Seva experience
* Sangha exposure
* Training history

---

# 38. Membership Application

The transition begins when the participant applies for NSS Membership through the common Membership process.

```text
KH000123
      ↓
Membership Application
```

Kishor participation itself does not create Membership.

---

# 39. Membership Approval

The common Membership authority determines whether the participant is approved.

Therefore:

```text
Kishor Participation
      ≠
NSS Membership
```

The Kishor module does not approve Membership.

---

# 40. Sangha Sevi ID Generation

After approved NSS Membership:

```text
KH000123
      ↓
Membership Approval
      ↓
SS000456
```

The Sangha Sevi ID is generated by the common Membership process.

---

# 41. Membership Transition Record

The transition is recorded through:

```text
kishor_membership_transition
```

The transition preserves the relationship between:

```text
Kishor Participant
        +
Sangha Sevi
```

The source explicitly freezes the KH → SS relationship.

---

# 42. Membership Type

The transition records the membership type granted by the Membership module.

Where applicable, this may be:

```text
REGULAR_MEMBER
```

or another approved Membership type.

The exact Membership type rules belong to the common Membership module.

---

# 43. Permanent KH → SS Relationship

After transition:

```text
KH000123
     │
     │ Permanent historical link
     ▼
SS000456
```

The KH ID remains valid as historical Kishor identity.

---

# 44. No Duplicate Person on Transition

Membership transition does not create a new Person.

The same Person is associated with:

```text
Kishor History
+
NSS Membership
```

---

# 45. Kishor History After Membership

After becoming an NSS Member, the participant's Kishor history remains available.

This includes:

* KH ID
* Annual registrations
* Participation history
* Guardian history
* Sakha context
* Membership transition

---

# 46. Membership Is Not Retroactive

Becoming an NSS Member does not rewrite earlier Kishor participation.

For example:

```text
2026 Kishor Participation
       ↓
2028 NSS Membership
```

does not convert the 2026 participation into NSS Membership participation.

The historical distinction remains intact.

---

# 47. Participant Lifecycle vs Membership Lifecycle

The two lifecycles remain separate:

```text
Kishor Lifecycle
      │
      ├── Annual Participation
      │
      └── Membership Transition
                 │
                 ▼
          Membership Lifecycle
```

The common Membership module owns the Membership lifecycle after transition.

---

# 48. Event Lifecycle vs Participant Lifecycle

Likewise:

```text
Participant Lifecycle
        ≠
Event Lifecycle
```

A completed event does not end the participant's Kishor identity.

A participant may return in a future year.

---

# 49. Event Registration Lifecycle

Conceptually:

```text
Registration Created
        ↓
Registration Available
        ↓
Participation
        ↓
Event Completed
        ↓
Historical Registration
```

The exact registration status vocabulary shall be finalized in the Business Rules document/common Event model.

---

# 50. Guardian Lifecycle

Conceptually:

```text
Guardian Required
        ↓
Sakha Assignment
        ↓
Active Guardian Assignment
        ↓
Guardian Change, if required
        ↓
Historical Assignment
```

The participant's KH identity is unaffected.

---

# 51. Sakha Association Lifecycle

Conceptually:

```text
Kishor Registration
        ↓
Sakha Association
        ↓
Annual Participation
        ↓
Historical Sakha Context
```

The Sakha association used for a historical registration must remain traceable.

---

# 52. No Automatic Membership

The following is prohibited:

```text
Kishor Puja Attendance
        ↓
Automatic NSS Membership
```

Membership requires the normal Membership process.

---

# 53. No Automatic KH Retirement After One Year

The participant does not cease to exist after one Kishor Puja.

For example:

```text
2026 Participation
        ↓
No 2027 Registration
        ↓
KH ID remains
```

The absence of a subsequent registration does not delete or invalidate the permanent KH identity.

---

# 54. No New KH ID After Gap

If the same participant returns after a gap:

```text
2026 → KH000123
2027 → No registration
2028 → KH000123
```

A new KH ID shall not be generated.

---

# 55. Person Lifecycle Dependency

If the Person becomes subject to a common Person lifecycle event, the Kishor records shall follow the applicable common Person lifecycle rules.

This document does not invent separate Kishor-specific death or other Person lifecycle rules.

The Person module remains authoritative for Person identity and lifecycle.

---

# 56. Historical Data Protection

Kishor records shall not be physically deleted merely because:

* A year has ended
* A participant skips a year
* A Guardian changes
* Sakha context changes
* The participant later becomes an NSS Member

---

# 57. Audit

The following lifecycle actions shall be auditable:

```text
First Kishor Registration
KH ID Generation
Sakha Association
Guardian Assignment
Guardian Change
Annual Registration
Participation
Membership Application Reference
Membership Transition
Administrative Correction
```

---

# 58. Lifecycle Status Boundary

Kishor participant status and event registration status are separate concepts.

```text
Participant Status
        ≠
Registration Status
        ≠
Attendance Status
        ≠
NSS Membership Status
```

These states must not be collapsed into a single status field.

---

# 59. Core Lifecycle Diagram

```text
PERSON
   │
   ▼
ELIGIBLE BOY
   │
   ▼
FIRST KISHOR REGISTRATION
   │
   ▼
KISHOR PARTICIPANT
   │
   ▼
KH000123
   │
   ▼
SAKHA ASSOCIATION
   │
   ▼
GUARDIAN ASSIGNMENT
   │
   ▼
ANNUAL KISHOR PUJA
   │
   ▼
EVENT REGISTRATION
   │
   ▼
PARTICIPATION
   │
   ├───────────────┐
   │               │
   ▼               ▼
NEXT YEAR       MEMBERSHIP
REGISTRATION    CONSIDERATION
   │               │
   ▼               ▼
SAME KH ID      APPLICATION
                   │
                   ▼
              APPROVAL
                   │
                   ▼
               SS000456
                   │
                   ▼
          MEMBERSHIP TRANSITION
```

---

# 60. Annual Participation Loop

```text
                 ┌──────────────────────┐
                 │                      │
                 ▼                      │
          Kishor Participant           │
                 │                      │
                 ▼                      │
          Annual Event Created          │
                 │                      │
                 ▼                      │
             Registration               │
                 │                      │
                 ▼                      │
            Participation              │
                 │                      │
                 ▼                      │
          Historical Record             │
                 │                      │
                 └──── Next Year ───────┘
```

The KH ID remains unchanged throughout the loop.

---

# 61. Guardian Lifecycle Diagram

```text
KISHOR PARTICIPANT
        │
        ▼
GUARDIAN REQUIRED
        │
        ▼
SAKHA ASSIGNS
        │
        ▼
NSS MEMBER OF SAME SAKHA
        │
        ▼
ACTIVE GUARDIAN
        │
        ├──────► Guardian Continues
        │
        └──────► Guardian Changed
                       │
                       ▼
                New Guardian
                       │
                       ▼
                History Preserved
```

---

# 62. Membership Transition Diagram

```text
KISHOR PARTICIPANT
       │
       │ KH000123
       ▼
LONG-TERM PARTICIPATION
       │
       ▼
MEMBERSHIP CONSIDERATION
       │
       ▼
APPLICATION
       │
       ▼
MEMBERSHIP APPROVAL
       │
       ▼
SANGHA SEVI
       │
       │ SS000456
       ▼
KISHOR → NSS TRANSITION
```

---

# 63. Identity Continuity

Throughout the lifecycle:

```text
Person
  │
  └── KH000123
         │
         ├── 2026
         ├── 2027
         ├── 2028
         │
         └── SS000456
```

Identity continuity is permanent.

---

# 64. Lifecycle Boundaries

The Kishor lifecycle deliberately does not define unsupported rules for:

```text
Specific age cutoff
Mandatory training hierarchy
Kishor-specific death status
Kishor-specific marriage status
Automatic inactivity
Automatic termination
Automatic membership
Automatic reactivation
```

Where such behavior is required, it must be established by an authoritative source or approved business rule.

---

# 65. Common Module Dependencies

The Kishor lifecycle depends on:

```text
Person
Family
Organization
Membership
Sangha Sevi
Attendance
Event
RBAC
Audit
```

The common modules remain authoritative for their respective domains.

---

# 66. Lifecycle Responsibility

| Lifecycle Area       | Owner                             |
| -------------------- | --------------------------------- |
| Person Identity      | Person                            |
| Family Relationship  | Family                            |
| Sakha Identity       | Organization                      |
| Kishor Identity     | Kishor                           |
| Kishor Event        | Kishor/Event                     |
| Registration         | Kishor                           |
| Attendance           | Attendance                        |
| Guardian Eligibility | Kishor + Membership/Organization |
| NSS Membership       | Membership                        |
| Sangha Sevi ID       | Membership                        |
| Access Control       | Administration/RBAC               |
| Audit                | Audit                             |

---

# 67. Final Lifecycle Model

The final Kishor lifecycle is:

```text
Person
  ↓
Eligible Participant
  ↓
First Registration
  ↓
KH ID
  ↓
Sakha Association
  ↓
Guardian Assignment
  ↓
Annual Event Registration
  ↓
Participation
  ↓
Historical Record
  ↓
Repeat in Future Years
  │
  └───────────────┐
                  │
                  ▼
          Membership Consideration
                  ↓
          Membership Application
                  ↓
          Membership Approval
                  ↓
             Sangha Sevi
                  ↓
           KH → SS Transition
```

---

# 68. Final Identity Rule

```text
KH000123
=
Permanent Kishor Identity
```

and:

```text
SS000456
=
NSS Membership Identity
```

The two identities are permanently linked after an approved transition.

---

# 69. Final Historical Rule

The system shall preserve:

```text
All Kishor registrations
All participation history
All Guardian assignments
All Sakha associations
All membership transition records
```

History is never silently rewritten or deleted.

---

# 70. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
