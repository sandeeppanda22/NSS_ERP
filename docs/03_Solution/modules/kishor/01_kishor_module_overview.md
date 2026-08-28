# NSS ERP — Kishor Puja Module Overview

**Document ID:** SOL-KISH-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kishor Puja  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Kishor Puja Module manages the NSS Kishor Puja program as an annual, event-based youth participation program for boys.

The module provides structured management of:

- Kishor identity
- Event registration
- Year-wise participation
- Sakha association
- Guardian assignment
- Event participation history
- Family visibility
- Future transition to NSS Membership

Kishor Puja is intentionally modeled differently from Kumari Sangha.

---

# 2. Institutional Position

Kishor Puja is not modeled as a permanent organizational unit equivalent to Kumari Sangha.

The frozen project position is:

```text
Kishor Puja
=
Annual Event / Activity
for Boys
```

Participants may come from different Sanghas and participate through the annual Kishor Puja event model.

---

# 3. Kishor vs Kumari

The two youth programs have different business models.

## Kumari Sangha

```text
Continuous Development Program

Own identity

Ongoing participation

Training

Dina-Lipi

Niyam Panchak

Dasa Sheela
```

## Kishor Puja

```text
Annual Event

Event Registration

Year-wise Participation

Guardian-Based

Sakha-Based Registration

Future Membership Pipeline
```

This distinction is frozen in the NSS V2 baseline.

---

# 4. Target Participants

The frozen Kishor model identifies the intended participants as boys, including:

* Boys from NSS families
* Sons of NSS members
* Boys nominated by parents
* Boys nominated by Sangha

Eligibility shall follow the approved Kishor rules.

The module shall not assume that every participant must already be an NSS member.

---

# 5. Kishor Identity

Every Kishor participant receives a dedicated Kishor ID.

Example:

```text
KH000001
KH000002
KH000003
```

The Kishor ID is:

* Unique
* Permanent
* Never reused
* Retained across years

The same Kishor ID is used when the participant attends Kishor Puja in subsequent years.

---

# 6. Kishor ID vs Sangha Sevi ID

Kishor ID and NSS Sangha Sevi ID are separate identities.

Example:

```text
Kishor ID

KH000123
```

Later:

```text
NSS Membership

SS000456
```

The relationship is permanently preserved.

A Kishor participant does not automatically receive an NSS Sangha Sevi ID.

---

# 7. Person Foundation

Every Kishor participant shall be associated with the common Person foundation.

Conceptually:

```text
PERSON
   │
   └── Kishor Participation
```

The Kishor module shall not create a duplicate Person identity.

The common principle remains:

```text
Person ≠ Member
```

---

# 8. Family Integration

Kishor participants may be connected to their family through the common Family module.

Conceptually:

```text
Family
   │
   └── Son
        │
        ▼
   Kishor Participant
        │
        ▼
      KH000123
```

The Family module remains the owner of:

* Family
* Family relationships
* Parent/child relationships
* Marriage relationships
* Family history

Kishor does not duplicate these structures.

---

# 9. Family Nomination

The frozen Kishor model supports nomination through the Family Portal.

Conceptually:

```text
Parent
   ↓
Nominate Son
   ↓
Kishor Registration
```

This provides a family-driven registration path.

---

# 10. Sakha Nomination

Kishor registration may also originate from the Sakha.

Conceptually:

```text
Sakha
   ↓
Nominate Boy
   ↓
Kishor Registration
```

The Sakha association is retained for operational ownership and reporting.

---

# 11. Sakha Association

Every Kishor registration shall be associated with a Sakha for operational ownership and reporting.

This does not mean Kishor Puja itself becomes a permanent Sakha-level organization.

The Sakha provides the participant's organizational context for the registration.

---

# 12. Cross-Sangha Participation

Participants may come from different Sanghas.

Therefore:

```text
Participant's Home Sakha
        ≠
Kishor Event Host
```

where applicable.

Participation in an event does not automatically transfer the participant's Sakha association.

---

# 13. Annual Event Model

Kishor Puja operates on a year-wise event model.

Example:

```text
KH000123

2026 Kishor Puja
2027 Kishor Puja
2028 Kishor Puja
```

The participant retains:

```text
KH000123
```

across all years.

Only event-specific participation changes.

---

# 14. Event Identity

Each Kishor Puja occurrence is represented as a distinct event.

Conceptually:

```text
Kishor Event
      │
      ├── Year
      ├── Event Date
      ├── Host Organization
      └── Registrations
```

The event remains historically identifiable.

---

# 15. Core Kishor Entities

The current frozen Kishor logical model identifies:

```text
kishor_participant

kishor_event

kishor_event_registration

kishor_membership_transition
```

These form the Kishor-specific domain model.

---

# 16. `kishor_participant`

Represents the permanent Kishor participant identity.

Conceptually:

```text
PERSON
   │
   ▼
KISHOR PARTICIPANT
   │
   ▼
KH000123
```

The participant record persists across multiple Kishor Puja years.

---

# 17. `kishor_event`

Represents an annual Kishor Puja event.

Examples:

```text
Kishor Puja 2026
Kishor Puja 2027
Kishor Puja 2028
```

The event is the central unit of year-wise participation.

---

# 18. `kishor_event_registration`

Represents the registration of a Kishor participant for a particular Kishor event.

Conceptually:

```text
KH000123
    ↓
Kishor Puja 2026
    ↓
Registration
```

The same participant may have multiple registration records across different annual events.

---

# 19. `kishor_membership_transition`

Represents the future transition from Kishor participation to NSS Membership.

Conceptually:

```text
KH000123
    ↓
NSS Membership Application
    ↓
Membership Approval
    ↓
SS000456
```

The relationship remains permanently traceable.

---

# 20. Guardian Model

Every Kishor participant must have an assigned Guardian.

This is a frozen rule.

The Guardian is:

```text
NSS Member
+
Member of the participant's Sakha
+
Assigned by the Sakha
```

The latest frozen Guardian Model supersedes earlier generic guardian proposals.

---

# 21. Guardian Assignment

Guardian assignment is operationally performed by the Sakha.

Conceptually:

```text
Kishor Participant
        ↓
Guardian Required
        ↓
Sakha Assigns Guardian
        ↓
NSS Member of Same Sakha
```

---

# 22. Guardian Identity

The Guardian reference shall point to the common NSS Sangha Sevi identity.

The frozen database impact identifies:

```text
guardian_sangha_sevi_pk
assigned_by_sakha_pk
guardian_assigned_date
```

and the Guardian references:

```text
sangha_sevi
```

rather than a generic Person record.

---

# 23. Guardian Responsibilities

The assigned Guardian is responsible for:

* Guidance
* Supervision
* Participation monitoring
* Communication with family
* Support during Kishor Puja
* Support during related activities

These responsibilities are part of the frozen Guardian Model.

---

# 24. Guardian and Parent Are Different Concepts

The Family module identifies the participant's family/parents.

The Kishor Guardian is an operational NSS role.

Therefore:

```text
Parent
   ≠
Assigned Kishor Guardian
```

unless the same person independently satisfies the Guardian rule.

The Guardian must satisfy the frozen NSS-member/Sakha assignment requirement.

---

# 25. Guardian Assignment History

Guardian assignment shall be historically traceable.

At minimum the system must preserve:

```text
Guardian
Assigned Sakha
Assignment Date
Assignment Authority
```

If the Guardian changes, the previous assignment shall remain historically available.

---

# 26. Guardian Change

A Guardian may be changed by the authorized Sakha process.

The new Guardian must satisfy the current Guardian eligibility rule.

Changing the Guardian shall not create:

```text
New Kishor ID
```

or:

```text
New Person
```

for the participant.

---

# 27. Event Registration

Registration connects:

```text
Kishor Participant
        ↓
Kishor Event
```

The registration may also retain the participant's operational Sakha and Guardian context as required by the frozen design.

---

# 28. Year-wise Participation

A participant may register in multiple annual Kishor Puja events.

Example:

```text
KH000123

2026 → Registered
2027 → Registered
2028 → Registered
```

The system must preserve each year's registration independently.

---

# 29. No New KH ID Each Year

The following is prohibited:

```text
2026 → KH000123
2027 → KH000456
```

for the same participant.

Instead:

```text
2026 → KH000123
2027 → KH000123
2028 → KH000123
```

The KH ID is permanent.

---

# 30. Event Participation History

The system shall preserve:

* Event
* Year
* Registration
* Guardian
* Sakha
* Participation status
* Relevant attendance/participation information
* Historical changes

where applicable.

---

# 31. Attendance Boundary

Kishor registration and attendance are different concepts.

```text
Registration
     ≠
Attendance
```

A registered participant may or may not attend.

The common Attendance framework shall be reused where attendance tracking is required.

---

# 32. Event Participation Boundary

Participation in one annual Kishor Puja does not automatically imply participation in the next year's event.

Each annual event has its own registration/participation record.

---

# 33. Event Host

A Kishor event may be hosted/organized by the relevant NSS organizational authority.

The host organization is part of the event context.

Hosting an event does not automatically change a participant's Sakha.

---

# 34. Participant's Sakha

The participant's Sakha remains the organizational context used for:

* Registration
* Guardian assignment
* Reporting
* Operational ownership

The participant does not become a member of the host Sakha merely by attending an event.

---

# 35. Kendra Visibility

Kendra-authorized users may view Kishor participants across all Sakhas.

This supports Kendra-wide monitoring and reporting.

---

# 36. Sakha Visibility

A Sakha-authorized user may view Kishor participants belonging to that Sakha.

The frozen visibility rule is:

```text
Sakha Secretary
      ↓
Only their Sakha's boys

Kendra
      ↓
All boys across all Sakhas
```

---

# 37. Guardian Visibility

An assigned Guardian may view the Kishor participants assigned to that Guardian, subject to common RBAC and privacy rules.

---

# 38. Family Visibility

Family members may view authorized Kishor information for their own family.

Potential information includes:

* Participant details
* Registration details
* Participation history
* Guardian details
* Participation status
* Membership transition status

Family access is restricted to the user's own family records.

---

# 39. Family Dashboard Integration

The Family Dashboard may show:

```text
Son
KH000456

Guardian
Assigned NSS Guardian

Participation
2025
2026

Status
Active / Applicable Status
```

This is part of the frozen Family First visibility model.

---

# 40. Future Membership Pipeline

Kishor Puja provides a potential pathway toward future NSS Membership.

Conceptually:

```text
Kishor
   ↓
Participation
   ↓
Development
   ↓
NSS Membership Application
   ↓
Membership Approval
   ↓
Sangha Sevi
```

This is a transition pathway, not automatic membership.

---

# 41. NSS Membership Application

A Kishor participant may later apply for NSS Membership where eligible.

The application is handled by the common Membership module.

Kishor does not approve NSS Membership.

---

# 42. Membership Approval

After NSS Membership approval:

```text
KH000123
      ↓
Membership Approved
      ↓
SS000456
```

The official Sangha Sevi identity is generated according to the common Membership rules.

---

# 43. Membership Transition History

The transition shall create a permanent historical link:

```text
KH000123
      │
      ▼
kishor_membership_transition
      │
      ▼
SS000456
```

The original Kishor history remains preserved.

---

# 44. Membership Type

The transition may preserve the membership type granted through the common Membership process.

Examples may include:

```text
REGULAR_MEMBER
PROBATIONARY_MEMBER
```

The Membership module remains authoritative for these types.

---

# 45. Kishor History After Membership

Becoming an NSS member shall not delete the participant's Kishor history.

The system shall preserve:

* KH ID
* Annual event registrations
* Participation history
* Guardian history
* Sakha history
* Membership transition

---

# 46. Kishor ID Permanence

The KH ID remains permanently associated with the participant's Kishor history.

Example:

```text
KH000123

2026
2027
2028
NSS Membership transition
```

All remain linked to the same KH ID.

---

# 47. No Duplicate Person on Transition

Transition to NSS Membership shall not create another Person.

The same Person remains associated with:

```text
Kishor History
+
NSS Membership
```

---

# 48. Kishor Status

Kishor participant status is distinct from NSS Membership status.

The exact final status master shall be defined in the Business Rules document.

The module shall not conflate:

```text
Kishor Participation Status
```

with:

```text
NSS Membership Status
```

---

# 49. Event Status

Kishor events shall have their own event lifecycle.

The exact common Event status model shall be used where applicable.

The event lifecycle shall remain distinct from the participant lifecycle.

---

# 50. Cancellation and Historical Integrity

If an annual Kishor event is cancelled or otherwise changed, its historical identity shall remain preserved.

Participant registration history shall not be silently deleted.

Detailed cancellation/rescheduling rules shall be finalized in the Kishor Business Rules document.

---

# 51. Common Module Integration

Kishor integrates with:

```text
Person
Family
Organization
Membership
Sangha Sevi
Attendance
Event
Reports
Administration/RBAC
Audit
```

Kishor-specific functionality shall not duplicate common foundation capabilities.

---

# 52. Governance Integration

If Kishor event organization requires governance or committee assignments, the common Governance framework shall be reused.

Kishor shall not create a separate governance architecture.

---

# 53. Security

Kishor access shall use the common NSS RBAC framework.

Authorization shall consider:

```text
User
+
Role
+
Organization Scope
+
Permission
```

No separate Kishor authentication system shall be created.

---

# 54. Audit

Kishor administrative actions shall use the common Audit framework.

Auditable actions include:

* Participant creation
* KH ID generation
* Event creation
* Registration
* Guardian assignment
* Guardian change
* Sakha association
* Membership transition
* Administrative corrections

---

# 55. Master Data

Kishor shall use master data where appropriate for:

```text
Event Type
Participant Status
Registration Status
Participation Status
Transition Type
Membership Type
```

The final Master Data Catalog remains authoritative.

---

# 56. Reports

The Kishor module shall support reporting such as:

```text
Total Kishor Participants
Annual Registrations
Participation by Sakha
Participation by Year
Guardian Assignment
Guardian Distribution
Family Participation
Membership Transitions
```

Reports shall respect RBAC and organizational scope.

---

# 57. Kishor Puja Portal

The UI baseline identifies a dedicated Kishor Puja portal.

Conceptually:

```text
Kishor Puja

Current Year Registrations

By Sakha

By Guardian

KH000101
KH000102
KH000103

Participation History
```

This is aligned with the annual-event Kishor model.

---

# 58. Family Portal

The Family Portal may provide:

```text
Kishor Registration
Participation History
Guardian Information
Status
Membership Transition
```

for the family's own Kishor participants.

---

# 59. No Permanent Kishor Sangha Requirement

The system shall not require creation of a permanent:

```text
Kishor Sangha
```

organizational unit merely to operate Kishor Puja.

The frozen source explicitly distinguishes Kishor Puja from the continuous organizational model of Kumari Sangha.

---

# 60. No Unified Youth Identity

Kishor shall retain its own:

```text
KH ID
```

It shall not be replaced by a generic:

```text
Youth ID
```

The project baseline explicitly preserves:

```text
Kumari ID ≠ Sangha Sevi ID
Kishor ID ≠ Sangha Sevi ID
```

and keeps the two youth domains distinct.

---

# 61. No Unified Youth Event Model

Kishor and Kumari may reuse common technical infrastructure, but their business models remain separate.

Kumari:

```text
Continuous Development
```

Kishor:

```text
Annual Event
```

The Solution layer shall preserve this distinction.

---

# 62. Core Kishor Architecture

```text
PERSON
   │
   ▼
KISHOR PARTICIPANT
   │
   │ KH000123
   │
   ├──────────────► KISHOR EVENT
   │                     │
   │                     ▼
   │             EVENT REGISTRATION
   │
   └──────────────► MEMBERSHIP TRANSITION
                         │
                         ▼
                    SANGHA SEVI
                         │
                         ▼
                      SS000456
```

Guardian and Sakha context are associated with the Kishor participation/registration model.

---

# 63. Core Entity Summary

```text
kishor_participant
    ↓
Permanent KH identity

kishor_event
    ↓
Annual Kishor Puja event

kishor_event_registration
    ↓
Year-specific participation

kishor_membership_transition
    ↓
KH → SS historical transition
```

---

# 64. Common Foundation Summary

```text
person
family_group
family_relationship
organization
membership
sangha_sevi
attendance
governance
audit
rbac
```

These remain common NSS modules.

---

# 65. Architectural Boundaries

The following distinctions are mandatory:

```text
Kishor Participant
        ≠
NSS Member

KH ID
        ≠
SS ID

Registration
        ≠
Attendance

Parent
        ≠
Operational Guardian

Participant's Sakha
        ≠
Event Host

Kishor Puja
        ≠
Kumari Sangha
```

---

# 66. History Preservation

The Kishor module follows:

```text
History Never Deleted
```

The system shall preserve:

* KH identity
* Annual registration history
* Guardian assignment history
* Sakha association history
* Participation history
* Membership transition history
* Audit history

---

# 67. Future Expansion

The architecture may later support additional Kishor-related activities/events without changing the permanent participant identity model.

Possible future events may be added through the common Event framework where approved.

No future event shall automatically create a new KH ID.

---

# 68. Out of Scope for This Overview

The following require detailed rules in later Kishor documents:

* Exact age eligibility
* Detailed registration approval workflow
* Detailed Guardian replacement workflow
* Event scheduling rules
* Event cancellation/rescheduling
* Attendance rules
* Event completion
* Detailed membership eligibility
* Detailed membership approval workflow
* Detailed reports
* Detailed permissions
* Physical database constraints

These shall not be invented in this overview.

---

# 69. Related Documents

The Kishor Solution documentation set is:

```text
docs/03_Solution/modules/kishor/

├── 01_kishor_module_overview.md
├── 02_kishor_erd.md
├── 03_kishor_lifecycle.md
├── 04_kishor_business_rules.md
└── 05_kishor_table_design.md
```

---

# 70. Source-Aligned Frozen Decisions

The following decisions are already frozen in the project source:

```text
✓ Kishor is annual/event-based
✓ Kishor is for boys
✓ KH identity
✓ KH ID is permanent
✓ KH ID retained across years
✓ Sakha-based registration/ownership
✓ Parent nomination
✓ Sakha nomination
✓ Mandatory assigned Guardian
✓ Guardian is NSS member of participant's Sakha
✓ Guardian assigned by Sakha
✓ Family visibility
✓ Kendra-wide visibility
✓ Sakha-scoped visibility
✓ Future KH → NSS Membership transition
✓ Permanent KH → SS relationship
✓ Kishor remains separate from Kumari
```

---

# 71. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

The Kishor Module Overview establishes the following fundamental model:

```text
                  PERSON
                    │
                    ▼
             KISHOR PARTICIPANT
                    │
                  KH ID
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
   ANNUAL EVENTS          GUARDIAN
          │                   │
          ▼                   ▼
   REGISTRATION          NSS MEMBER
          │
          │
          ▼
   FUTURE MEMBERSHIP
          │
          ▼
      SANGHA SEVI
          │
          ▼
       SS ID
```

---

# End of Document
