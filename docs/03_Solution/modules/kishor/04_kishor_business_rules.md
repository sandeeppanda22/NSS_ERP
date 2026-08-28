# NSS ERP — Kishor Puja Business Rules

**Document ID:** SOL-KISH-004  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kishor Puja  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing Kishor Puja within NSS ERP.

It covers:

- Kishor identity
- Eligibility
- Registration
- Sakha ownership
- Guardian assignment
- Annual events
- Participation
- Attendance relationship
- Family visibility
- Sakha/Kendra visibility
- Membership transition
- History
- Audit
- Common-module integration

---

# 2. KISH-001 — Kishor Puja Is Event-Based

Kishor Puja shall be modeled as an annual NSS event/activity for boys.

It shall not be modeled as a permanent organizational unit equivalent to Kumari Sangha.

This is a frozen NSS V2 decision.

---

# 3. KISH-002 — Kishor and Kumari Are Separate Domains

Kishor Puja and Kumari Sangha shall remain separate business modules.

```text
Kumari Sangha
=
Continuous Development Program

Kishor Puja
=
Annual Event-Based Program
```

They may reuse common foundation services but shall not be treated as the same business lifecycle.

---

# 4. KISH-003 — Eligible Population

The frozen Kishor model identifies eligible participants as:

* Boys from NSS families
* Sons of NSS members
* Boys nominated by parents
* Boys nominated by Sangha

The exact detailed age cutoff is not frozen in the current source and shall not be invented here.

---

# 5. KISH-004 — Person Foundation

Every Kishor participant shall be associated with the common Person record.

Kishor shall not create a duplicate person identity.

```text
Person
   ↓
Kishor Participant
```

---

# 6. KISH-005 — Kishor Identity

Every Kishor participant shall receive a unique Kishor ID.

Example:

```text
KH000001
KH000002
KH000003
```

---

# 7. KISH-006 — KH ID Is Permanent

Once generated, the KH ID shall:

* Remain unique
* Never be reused
* Remain associated with the same participant
* Remain valid across multiple Kishor Puja years

This is frozen.

---

# 8. KISH-007 — One Person One Kishor Identity

The same Person shall not receive multiple active Kishor IDs.

A participant returning in a later year shall use the existing KH ID.

---

# 9. KISH-008 — Annual Participation Uses Same KH ID

Example:

```text
KH000123

2026 Kishor Puja
2027 Kishor Puja
2028 Kishor Puja
```

All records belong to the same Kishor participant.

---

# 10. KISH-009 — No New KH ID Per Event

Registration for another annual event shall never generate a new KH ID.

```text
2026 → KH000123
2027 → KH000123
2028 → KH000123
```

---

# 11. KISH-010 — Parent Nomination

Parents may nominate a boy through the Family Portal.

```text
Parent
   ↓
Nominate Son
   ↓
Kishor Registration
```

This is a frozen registration route.

---

# 12. KISH-011 — Sakha Nomination

A Sakha may nominate a boy.

```text
Sakha
   ↓
Nominate Boy
   ↓
Kishor Registration
```

This is a separate registration route from family nomination.

---

# 13. KISH-012 — Registration Does Not Require Existing NSS Membership

A boy may participate in Kishor Puja without already being an NSS Member.

Kishor participation and NSS Membership are separate concepts.

---

# 14. KISH-013 — Kishor Is Not an NSS Membership Category

Kishor participation shall not be treated as:

* Regular Membership
* Probationary Membership
* Associate Membership
* Any other NSS Membership type

---

# 15. KISH-014 — Sakha Association Is Mandatory

Every Kishor registration must be associated with a Sakha.

This remains mandatory even when registration originated from:

```text
Parent nomination
```

or:

```text
Sakha nomination
```

The Sakha association exists for operational ownership and reporting.

---

# 16. KISH-015 — Sakha Ownership

The Sakha associated with a Kishor registration is used for:

* Operational ownership
* Reporting
* Visibility
* Guardian assignment
* Sakha-level administration

---

# 17. KISH-016 — Participant Sakha vs Event Host

The participant's Sakha and event host are separate concepts.

```text
Participant Sakha
      ≠
Event Host
```

Participating in an event hosted elsewhere does not automatically transfer Sakha affiliation.

---

# 18. KISH-017 — Cross-Sangha Participation

Participants may come from different Sanghas.

A Kishor event may therefore contain participants from multiple Sakhas.

Each participant retains the applicable Sakha association.

---

# 19. KISH-018 — Historical Sakha Context

Historical registration records shall preserve the Sakha context applicable to that registration.

Example:

```text
2026 → Sakha A
2027 → Sakha A
2028 → Sakha B
```

The 2026 registration shall not be rewritten merely because the participant later changes organizational association.

---

# 20. KISH-019 — Guardian Is Mandatory

Every Kishor participant must have an assigned Guardian.

This is a frozen rule.

---

# 21. KISH-020 — Guardian Must Be an NSS Member

The operational Guardian must be an NSS Member.

The Guardian shall therefore be represented through the common Sangha Sevi/Membership identity.

---

# 22. KISH-021 — Guardian Must Belong to Participant's Sakha

The assigned Guardian must be an NSS Member of the participant's Sakha.

```text
Participant
   ↓
Sakha A

Guardian
   ↓
NSS Member of Sakha A
```

This is part of the frozen Guardian Model.

---

# 23. KISH-022 — Guardian Assigned by Sakha

The Guardian shall be assigned by the Sakha.

The assignment shall not be treated as an unrestricted parent-entered field.

---

# 24. KISH-023 — Guardian Is Not Necessarily Parent

The operational Guardian is not necessarily:

* Father
* Mother
* Legal guardian

A parent may serve as Guardian only if the person independently satisfies the frozen NSS-member/Sakha requirement.

The current frozen rule supersedes the earlier generic Guardian proposal.

---

# 25. KISH-024 — Guardian Responsibilities

The assigned Guardian is responsible for:

* Guidance
* Supervision
* Participation monitoring
* Communication with family
* Support during Kishor Puja
* Support during related activities

---

# 26. KISH-025 — Guardian Assignment Date

The system shall record the effective Guardian assignment date.

---

# 27. KISH-026 — Guardian Assignment Authority

The system shall retain the Sakha responsible for assigning the Guardian.

---

# 28. KISH-027 — Guardian Change

An authorized Sakha may change the assigned Guardian where required.

Changing the Guardian shall not create:

* New Person
* New KH ID
* New Kishor participant

---

# 29. KISH-028 — Guardian History

Guardian changes shall preserve historical information.

The previous Guardian assignment shall remain traceable according to the project audit/history standards.

---

# 30. KISH-029 — Annual Event

Each Kishor Puja occurrence shall be represented as a separate annual event.

Examples:

```text
Kishor Puja 2026
Kishor Puja 2027
Kishor Puja 2028
```

---

# 31. KISH-030 — Event Identity

Each annual Kishor event shall have its own event identity.

The event identity shall remain historically traceable after completion.

---

# 32. KISH-031 — Event Year

Each Kishor event shall record its applicable year/financial year.

This supports year-wise reporting.

---

# 33. KISH-032 — Event Host

Each Kishor event shall identify its authorized host organization.

The host organization is distinct from individual participant Sakha associations.

---

# 34. KISH-033 — Event Registration

A Kishor participant registers separately for each annual event.

```text
KH000123
   ↓
Kishor Puja 2026
   ↓
Registration
```

---

# 35. KISH-034 — One Registration Per Participant Per Event

A participant shall not have duplicate active registrations for the same Kishor event.

Conceptually:

```text
KH000123 + Kishor Puja 2026
=
One Registration
```

---

# 36. KISH-035 — Multiple Event Registrations

The same participant may register for multiple annual events.

```text
KH000123
 ├── 2026 Registration
 ├── 2027 Registration
 └── 2028 Registration
```

---

# 37. KISH-036 — Registration Does Not Equal Attendance

Registration and attendance are separate concepts.

```text
Registration
   ≠
Attendance
```

A registered participant may fail to attend.

---

# 38. KISH-037 — Registration Does Not Equal Participation

Registration establishes eligibility/intent to participate in the event.

Actual participation must be represented separately where the applicable workflow requires it.

---

# 39. KISH-038 — Attendance Uses Common Attendance

Where Kishor event attendance is recorded, the common Attendance framework shall be reused.

The Kishor module shall not create an isolated attendance architecture without an approved requirement.

---

# 40. KISH-039 — No Attendance-Based Membership

Attendance at Kishor Puja shall not automatically create NSS Membership.

```text
Kishor Attendance
      ≠
NSS Membership
```

---

# 41. KISH-040 — No Attendance-Based New KH ID

Attendance in another event never generates a new KH ID.

---

# 42. KISH-041 — Event Completion

After an event is completed, its registration and participation history shall remain available for reporting and historical purposes.

---

# 43. KISH-042 — No Automatic Retirement After One Year

Failure to participate in a particular year shall not automatically invalidate the participant's KH identity.

Example:

```text
2026 → Participated
2027 → No Registration
2028 → Participated
```

The participant remains:

```text
KH000123
```

---

# 44. KISH-043 — Return After Participation Gap

If the participant returns after one or more years, the existing KH ID shall be reused.

No new participant identity shall be created.

---

# 45. KISH-044 — Family Visibility

Every NSS family shall be able to view the Kishor participation details of its own family members.

The frozen family visibility model includes:

* Participant details
* Registration details
* Activity history where applicable
* Training history where applicable
* Participation status
* Assigned Guardian
* Membership transition status

Access is restricted to the family's own records.

---

# 46. KISH-045 — Family Is Primary Visibility Unit

Parents/family members should not require separate Sakha permissions to view their own children's Kishor information.

Family access remains restricted to the user's own family.

---

# 47. KISH-046 — Sakha Visibility

A Sakha may view Kishor participants and registrations belonging to that Sakha.

Sakha visibility includes:

* Total registrations
* Active registrations
* Year-wise registrations
* Participant list
* Guardian details
* Participation status

---

# 48. KISH-047 — Sakha Cannot View Other Sakha's Participants

A Sakha-level user shall not automatically receive visibility into another Sakha's Kishor participants.

Organizational scope shall be enforced through common RBAC.

---

# 49. KISH-048 — Kendra Visibility

Kendra-authorized users may view Kishor information across all Sakhas.

This includes:

* All registrations
* All Sakhas
* State-wise reports
* District-wise reports
* Year-wise reports
* Complete participant history

---

# 50. KISH-049 — Guardian Visibility

An assigned Guardian may view authorized information for participants assigned to that Guardian.

Access remains subject to common RBAC and privacy rules.

---

# 51. KISH-050 — Guardian Cannot Change Own Assignment

A Guardian shall not automatically become the authority for changing their own assignment.

Guardian assignment remains a Sakha administrative action.

---

# 52. KISH-051 — Membership Is Separate

Kishor participation shall remain separate from NSS Membership.

```text
Kishor Participant
      ≠
NSS Member
```

---

# 53. KISH-052 — Membership Application

A Kishor participant may later apply for NSS Membership where eligible.

The application shall use the common Membership workflow.

---

# 54. KISH-053 — Membership Approval

Kishor participation does not itself approve NSS Membership.

Membership approval belongs to the common Membership authority.

---

# 55. KISH-054 — Long-Term Kishor Participation

Long-term Kishor participants may be considered for NSS Membership.

The source specifically recognizes:

* NSS philosophy exposure
* Discipline
* Seva experience
* Sangha exposure
* Training history

as relevant considerations.

---

# 56. KISH-055 — Regular Membership Consideration

Long-term Kishor participants may be considered for Regular Membership without mandatory probation where the applicable Membership authority approves.

The Membership module remains authoritative.

---

# 57. KISH-056 — No Automatic Membership

The following is prohibited:

```text
Kishor Participation
      ↓
Automatic NSS Membership
```

Membership requires the normal approval process.

---

# 58. KISH-057 — Sangha Sevi ID

After approved NSS Membership, the common Membership module generates the Sangha Sevi ID.

Example:

```text
KH000123
    ↓
Membership Approval
    ↓
SS000456
```

---

# 59. KISH-058 — KH → SS Transition

The transition shall be recorded through the Kishor membership transition mechanism.

The relationship between KH ID and Sangha Sevi ID shall be permanently traceable.

---

# 60. KISH-059 — Transition Record

The transition record shall preserve, at minimum:

```text
Kishor Participant
Sangha Sevi
Transition Date
Membership Type Granted
```

---

# 61. KISH-060 — No Duplicate Person on Transition

Membership transition shall not create a second Person record.

The same Person remains associated with both histories.

---

# 62. KISH-061 — KH History Preserved After Membership

After becoming an NSS Member, the complete Kishor history remains available.

This includes:

* KH ID
* Annual registrations
* Participation history
* Guardian history
* Sakha history
* Membership transition

---

# 63. KISH-062 — Membership Does Not Rewrite Kishor History

If:

```text
2026 → Kishor
2028 → NSS Member
```

the 2026 Kishor record remains a Kishor record.

It shall not be retroactively converted into NSS Membership participation.

---

# 64. KISH-063 — KH and SS Identities Remain Separate

```text
KH000123
    ≠
SS000456
```

The two identities are independently meaningful.

The transition record provides the historical relationship.

---

# 65. KISH-064 — No Unified Youth Identity

The Kishor module shall retain its own KH identity.

It shall not replace KH ID with a generic Youth ID.

The project source explicitly distinguishes Kishor's event-based model from Kumari's continuous development model.

---

# 66. KISH-065 — No Unified Youth Business Module

Kishor and Kumari may share technical foundation services but remain separate business modules.

---

# 67. KISH-066 — No Duplicate Family Structures

The Kishor module shall not create:

```text
kishor_family
kishor_parent
kishor_family_relationship
```

The common Family module owns family relationships.

---

# 68. KISH-067 — No Duplicate Person Structure

The Kishor module shall not create:

```text
kishor_person
```

Person identity belongs to the common Person module.

---

# 69. KISH-068 — No Duplicate Organization Structure

The Kishor module shall not create:

```text
kishor_sakha
kishor_organization
```

The common Organization module remains authoritative.

---

# 70. KISH-069 — No Duplicate Membership Structure

The Kishor module shall not create:

```text
kishor_membership
kishor_sangha_sevi
```

for NSS Membership purposes.

The common Membership module owns NSS Membership.

---

# 71. KISH-070 — No Duplicate Guardian Identity

Guardian identity shall reference the common Sangha Sevi identity.

The frozen database rule specifies:

```text
guardian_sangha_sevi_pk
```

rather than a generic Person reference.

---

# 72. KISH-071 — RBAC Reuse

Kishor access shall use the common NSS RBAC framework.

No separate Kishor authentication or authorization framework shall be created.

---

# 73. KISH-072 — Organizational Scope

Kishor authorization shall respect organizational scope.

Examples:

```text
Family
   → Own Family

Sakha
   → Own Sakha

Kendra
   → All Sakhas
```

---

# 74. KISH-073 — Audit

The following actions shall be auditable:

* Kishor creation
* KH ID generation
* Registration
* Sakha association
* Guardian assignment
* Guardian change
* Event creation
* Event changes
* Participation
* Membership transition
* Administrative corrections

---

# 75. KISH-074 — History Never Deleted

Kishor historical records shall not be physically deleted merely because:

* Event completed
* Participant skipped a year
* Guardian changed
* Sakha changed
* Participant became an NSS Member

---

# 76. KISH-075 — Historical Registration Preservation

Each annual registration remains historically identifiable.

Example:

```text
KH000123
 ├── 2026 Registration
 ├── 2027 Registration
 └── 2028 Registration
```

---

# 77. KISH-076 — Historical Guardian Context

Where a Guardian changes between years, the system shall preserve the Guardian applicable to historical records where required for accurate reporting.

---

# 78. KISH-077 — Historical Sakha Context

Where the participant's Sakha context changes, historical registrations shall preserve their original organizational context.

---

# 79. KISH-078 — Event Host History

Changing organizational arrangements in later years shall not rewrite the host organization recorded against completed historical events.

---

# 80. KISH-079 — Event Cancellation/Change

If the common Event framework permits event cancellation or rescheduling, the Kishor event identity and historical records shall be preserved.

Detailed cancellation/rescheduling rules shall follow the common Event framework unless Kishor-specific rules are approved.

---

# 81. KISH-080 — Status Separation

The following concepts shall remain separate:

```text
Participant Status
Registration Status
Participation Status
Attendance Status
NSS Membership Status
```

One status shall not automatically substitute for another.

---

# 82. KISH-081 — No Attendance-Based Termination

Absence from one or more Kishor events shall not automatically terminate the permanent KH identity.

No such automatic termination rule is frozen in the current source.

---

# 83. KISH-082 — No Attendance-Based Reactivation

Because no attendance-based termination is frozen, no attendance-based automatic reactivation shall be introduced.

---

# 84. KISH-083 — No Unsupported Age Rule

The system shall not hard-code an age cutoff unless an authoritative requirement defines one.

---

# 85. KISH-084 — No Unsupported Training Hierarchy

The current source does not freeze a mandatory Kishor training hierarchy.

The ERP shall not invent:

```text
Orientation
→ Basic
→ Advanced
→ Leadership
```

as a mandatory Kishor lifecycle.

---

# 86. KISH-085 — Activity/Training History

Where activities or training are recorded for Kishor participants, the history shall remain available for reporting.

Such records shall not automatically change the participant's identity or Membership status.

---

# 87. KISH-086 — Family Dashboard Integration

The Family Dashboard may show:

```text
Son
KH000123

Kishor Puja 2025
Kishor Puja 2026

Assigned Guardian

Participation History
```

This aligns with the frozen Family First visibility model.

---

# 88. KISH-087 — Sakha Dashboard Integration

The Sakha Dashboard may show:

```text
Kishor Registrations

Current Year

Previous Years

Assigned Guardians

Participation
```

but only within authorized Sakha scope.

---

# 89. KISH-088 — Kendra Dashboard Integration

The Kendra Dashboard may show:

```text
Total Kishor Participants
Registrations by Sakha
Year-wise Participation
Guardian Distribution
District-wise Reports
State-wise Reports
Membership Transitions
```

---

# 90. KISH-089 — Reports Respect RBAC

Kishor reports shall respect the user's organizational authorization.

A report shall not expose participants outside the user's permitted scope.

---

# 91. KISH-090 — Master Data Driven

Where configurable classifications are required, the Kishor module shall use common master-data standards.

Examples:

```text
Registration Status
Participation Status
Event Status
Transition Type
```

---

# 92. KISH-091 — Common Event Framework

Where the common Event framework provides suitable functionality, Kishor shall reuse it rather than create duplicate event infrastructure.

Kishor-specific business rules remain authoritative over generic event behavior.

---

# 93. KISH-092 — Common Attendance Framework

Where attendance is required, the common Attendance module shall be used.

Kishor-specific attendance behavior shall only be added where approved.

---

# 94. KISH-093 — Common Family Framework

Family relationships remain owned by the Family module.

Kishor only consumes those relationships for visibility and participation context.

---

# 95. KISH-094 — Common Membership Framework

NSS Membership remains owned by the Membership module.

Kishor records only the transition relationship.

---

# 96. KISH-095 — Common Organization Framework

Sakha and host organization identities remain owned by the Organization module.

---

# 97. KISH-096 — Common Audit Framework

Kishor actions shall follow project-wide audit standards.

---

# 98. KISH-097 — No SQL in Business Rules

This document defines business rules only.

It does not define:

* PostgreSQL DDL
* CREATE TABLE
* ALTER TABLE
* SQL indexes
* SQL triggers
* Django migrations

---

# 99. KISH-098 — Core Kishor Entities

The current Kishor-specific logical model consists of:

```text
kishor_participant
kishor_event
kishor_event_registration
kishor_membership_transition
```

This is the current frozen Kishor architecture.

---

# 100. KISH-099 — Permanent Identity Architecture

The final identity relationship is:

```text
PERSON
   ↓
KISHOR PARTICIPANT
   ↓
KH000123
```

and, after approved Membership transition:

```text
KH000123
   ↓
Transition
   ↓
SS000456
```

---

# 101. KISH-100 — Final Kishor Lifecycle Rule

The complete business flow is:

```text
Eligible Boy
      ↓
Parent / Sakha Nomination
      ↓
Kishor Registration
      ↓
KH ID
      ↓
Sakha Association
      ↓
Guardian Assignment
      ↓
Annual Kishor Puja
      ↓
Event Registration
      ↓
Participation
      ↓
Historical Record
      ↓
Future Annual Participation
      │
      ▼
Membership Consideration
      ↓
NSS Membership Application
      ↓
Membership Approval
      ↓
Sangha Sevi ID
      ↓
Permanent KH → SS Transition
```

---

# 102. Final Frozen Rules Summary

The following are the core frozen Kishor decisions:

```text
✓ Kishor Puja is annual/event-based

✓ Kishor is for boys

✓ Parent nomination is supported

✓ Sakha nomination is supported

✓ KH ID is unique

✓ KH ID is permanent

✓ KH ID is retained across years

✓ Every registration is associated with a Sakha

✓ Every participant has an assigned Guardian

✓ Guardian is an NSS Member of participant's Sakha

✓ Guardian is assigned by the Sakha

✓ Guardian responsibilities are defined

✓ Family can view its own Kishor participants

✓ Sakha sees its own participants

✓ Kendra sees participants across Sakhas

✓ Registration is separate from attendance

✓ Kishor participation does not automatically create Membership

✓ Long-term Kishor participants may be considered for Membership

✓ KH → SS transition is permanently traceable

✓ Historical records are preserved
```

These decisions are directly supported by the frozen project source.

---

# 103. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
