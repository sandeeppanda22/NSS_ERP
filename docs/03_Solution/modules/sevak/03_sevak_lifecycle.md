# NSS ERP — Sevak Sangha Lifecycle

**Document ID:** SOL-SEV-003  
**Version:** 2.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Sevak Participation Lifecycle

---

# 1. Purpose

This document defines the lifecycle of a person's participation in Sevak Sangha.

It describes:

- Entry into Sevak Sangha
- ACTIVE participation
- INACTIVE participation
- Membership Transfer
- Death
- Reactivation
- Sakha association history
- Seva relationship
- Event participation relationship
- Historical preservation

Detailed business rules are maintained in:

```text
05_sevak_business_rules.md
```

Operational event participation is maintained in:

```text
04_sevak_participation_rules.md
```

---

# 2. Fundamental Identity Model

Sevak Sangha does not create a separate NSS identity.

The lifecycle follows:

```text
Person
   ↓
NSS Membership
   ↓
Sangha Sevi ID
   ↓
Sevak Participation
```

Therefore:

```text
Person ≠ Sevak Participation

NSS Membership ≠ Sevak Participation

Sevak Participation ≠ Separate Membership
```

The Sangha Sevi ID remains the authoritative NSS Membership identity.

---

# 3. Entry Requirement

NSS Membership is mandatory for Sevak participation.

The core lifecycle is:

```text
Person
   ↓
NSS Member
   ↓
Eligible NSS Member
   ↓
Sevak Enrollment
   ↓
ACTIVE Sevak Participation
```

A non-member shall not be registered as a Sevak.

---

# 4. Eligibility

The current core eligibility model is defined by:

```text
05_sevak_business_rules.md
```

The current frozen rule is:

```text
Eligible NSS Member
+
Applicable Sevak eligibility
        ↓
May be enrolled as Sevak
```

There is no additional Sevak-specific age restriction beyond the applicable NSS Membership eligibility rules.

The older lifecycle concept that independently listed:

```text
Youth
Teenagers
Students
```

as Sevak eligibility categories is superseded.

---

# 5. Enrollment

An eligible NSS Member may be directly enrolled as a Sevak by an authorized user.

Lifecycle:

```text
Eligible NSS Member
        ↓
Direct Enrollment
        ↓
ACTIVE Sevak Participation
```

No separate application-review process is required by the current core Sevak enrollment model.

Enrollment must be:

* Authorized
* Recorded
* Auditable
* Historically preserved

---

# 6. First Sevak Enrollment Date

The first enrollment date is a permanent historical milestone.

Example:

```text
01-Jan-2020
    ↓
First Sevak Enrollment
```

The date does not change because of:

* Sakha Transfer
* Inactivation
* Reactivation
* Later Sevak association

Therefore:

```text
First Sevak Enrollment Date
        =
Beginning of overall Sevak history
```

---

# 7. Initial ACTIVE State

After successful direct enrollment:

```text
Sevak Participation
        ↓
ACTIVE
```

The only current Sevak participation statuses are:

```text
ACTIVE
INACTIVE
```

There is no:

```text
PROBATIONARY_SEVAK
REGULAR_SEVAK
COMPLETED
WITHDRAWN
```

status in the Sevak participation lifecycle.

---

# 8. Core Lifecycle

The normal lifecycle is:

```text
NSS Membership
       │
       ▼
Eligibility
       │
       ▼
Sevak Enrollment
       │
       ▼
ACTIVE
       │
       ├──────────────► INACTIVE
       │                    │
       │                    ▼
       │              Reactivation Review
       │                    │
       │                    ▼
       │                  ACTIVE
       │
       ├──────────────► Membership Transfer
       │                    │
       │                    ▼
       │          Old Participation INACTIVE
       │                    │
       │                    ▼
       │          New Sakha Evaluation
       │
       └──────────────► Death
                            │
                            ▼
                         INACTIVE
                         DECEASED
```

---

# 9. ACTIVE → INACTIVE

A Sevak may become INACTIVE through:

### Manual lifecycle action

```text
ACTIVE
   ↓
Authorized User
   ↓
INACTIVE
```

A mandatory reason is required.

### System-generated lifecycle action

```text
ACTIVE
   ↓
Membership Transfer
   ↓
INACTIVE
```

or:

```text
ACTIVE
   ↓
Person/Membership Death Lifecycle
   ↓
INACTIVE
```

System-generated changes require no manual Sevak intervention.

---

# 10. Manual Inactivation

For manual inactivation:

```text
Source = MANUAL
```

A reason is mandatory.

Permitted manual reasons are:

```text
NO_LONGER_PARTICIPATING
PERSONAL_REASON
LONG_TERM_ABSENCE
OTHER
```

The inactivation event must be audited.

---

# 11. Transfer-Triggered Inactivation

Membership Transfer is authoritative for Sakha association.

When a member transfers:

```text
Sakha A
   ↓
Sakha B
```

the old Sevak participation is automatically made:

```text
Status = INACTIVE
Source = SYSTEM
Reason = TRANSFERRED_TO_OTHER_SAKHA
```

No manual Sevak intervention is required.

---

# 12. New Sakha Evaluation

After Membership Transfer, the system evaluates whether the new Sakha has a Sevak Sangha.

### New Sakha has Sevak Sangha

```text
Membership transferred
        ↓
New Sakha has Sevak Sangha
        ↓
New ACTIVE Sevak participation may be created
```

### New Sakha does not have Sevak Sangha

```text
Membership transferred
        ↓
New Sakha has no Sevak Sangha
        ↓
No new current Sevak participation
```

The previous Sevak participation remains historical.

---

# 13. No Independent Sevak Transfer

There is no separate:

```text
SEVAK_TRANSFER
```

workflow.

The authoritative process is:

```text
NSS Membership Transfer
        ↓
Current Sakha changes
        ↓
Sevak lifecycle responds automatically
```

This prevents conflicting Sakha identities between Membership and Sevak Sangha.

---

# 14. Sakha Association History

Sevak Sakha association is maintained as effective-dated history.

Example:

```text
Sakha A
01-Jan-2020 → 15-Aug-2026

Sakha B
15-Aug-2026 → Current
```

The historical Sakha association shall remain permanently available.

The current Sakha is derived from the applicable current association.

---

# 15. Sakha Without Sevak Sangha

If the current Sakha does not have a Sevak Sangha:

```text
Current Membership
        ↓
Sakha has no Sevak Sangha
        ↓
No current local Sevak participation
```

Previous Sevak history remains preserved.

The absence of a local Sevak Sangha does not delete the person's historical Sevak record.

---

# 16. Death Lifecycle

Death is a global Person/Membership lifecycle event.

It is not a Sevak-specific manual action.

When the authoritative Person/Membership lifecycle records:

```text
DECEASED
```

the Sevak participation is automatically changed to:

```text
Status = INACTIVE
Reason = DECEASED
Source = SYSTEM
```

No manual Sevak approval is required.

---

# 17. Death Is Global

Death status applies to the person's identity across the ERP.

Therefore, the system shall not limit deceased status to Sevak records.

The Sevak lifecycle consumes the authoritative Person/Membership death event.

Conceptually:

```text
Person Lifecycle
      ↓
DECEASED
      ↓
All applicable participation modules
      ↓
Apply their lifecycle rules
```

---

# 18. No Reactivation After Death

A person whose authoritative lifecycle status is:

```text
DECEASED
```

shall not be reactivated as a Sevak through the normal Sevak reactivation workflow.

Any correction of an erroneous death record must occur through the authoritative Person/Membership lifecycle correction process.

The Sevak record follows that authoritative correction.

---

# 19. INACTIVE State

INACTIVE means the person does not currently have active Sevak participation.

It does not mean:

```text
Membership Deleted
```

or:

```text
Person Deleted
```

or:

```text
Historical Sevak Record Deleted
```

The historical participation remains available.

---

# 20. No Attendance-Based Inactivation

Attendance does not automatically cause:

```text
ACTIVE → INACTIVE
```

There is no attendance threshold.

In particular, the previously considered two-month inactivity rule is withdrawn.

The system shall not automatically inactivate a Sevak because of:

* Missing Sakha sessions
* Missing Sunday sessions
* Missing Anchalika/Zilla Puja
* Number of consecutive absences
* Number of months without attendance

---

# 21. INACTIVE Participation

INACTIVE does not automatically prohibit attendance at a Sevak activity where the applicable event rules permit participation.

Therefore:

```text
INACTIVE
   ↓
May Attend Applicable Sevak Event
```

Attendance does not itself change status.

---

# 22. INACTIVE Attendance

When an INACTIVE Sevak attends an applicable Sevak event:

```text
Attendance Recorded
        ↓
Status remains INACTIVE
        ↓
Reactivation Review
```

The system shall not perform:

```text
INACTIVE + ATTENDANCE
        =
ACTIVE
```

automatically.

---

# 23. Reactivation Review

Attendance by an INACTIVE Sevak may create a reactivation review cycle.

Lifecycle:

```text
INACTIVE
   ↓
Attends Applicable Event
   ↓
Attendance Recorded
   ↓
Reactivation Review Cycle
   ↓
Authorized Review
   ├── Keep INACTIVE
   └── Reactivate ACTIVE
```

Only one OPEN review cycle may exist for a Sevak.

Additional attendance while the review is open attaches to the existing review cycle.

---

# 24. Reactivation

Reactivation is an authorized manual action:

```text
INACTIVE
   ↓
Authorized Review
   ↓
ACTIVE
```

No reason is mandatory for reactivation.

The action must be audited.

The original First Sevak Enrollment Date remains unchanged.

---

# 25. Reactivation Does Not Rewrite History

When a Sevak is reactivated:

```text
First Enrollment
      ↓
Historical INACTIVE Period
      ↓
Reactivation
      ↓
ACTIVE
```

The previous inactive period remains historical.

The system shall not rewrite the person's Sevak history as though the person had remained continuously active.

---

# 26. Reactivation Review Closure

After an authorized reviewer makes a decision:

```text
OPEN
   ↓
CLOSED
```

The closed review cycle remains permanently available.

If the Sevak remains INACTIVE and later attends another applicable event after the previous review has closed:

```text
New Attendance
      ↓
New Review Cycle
```

may be created.

---

# 27. Event Participation

Sevak lifecycle and event participation are separate.

The lifecycle provides the current participation status.

The event framework determines:

* Event eligibility
* Visibility
* Intention
* Probable attendance
* Actual attendance

These must not be merged into the Sevak status.

---

# 28. Current Sevak Event Types

The current approved Sevak event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

and:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

They have separate detailed business rules.

---

# 29. Sakha-Level Event Relationship

A Sakha-Level Sevak Sangha Session is a local operational activity.

Its rules are maintained in:

```text
sangha/01_sakha_sevak_sangha_session_rules.md
```

The lifecycle document does not duplicate:

* Session scheduling
* Participant eligibility
* Probable attendance
* Intention
* Cancellation
* Reconciliation

---

# 30. Anchalika/Zilla Event Relationship

The Anchalika/Zilla Sevak Sangha Puja is a larger periodic event.

Its rules are maintained in:

```text
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
```

The lifecycle document does not duplicate its detailed event rules.

---

# 31. Cross-Anchalika/Zilla Attendance

A Sevak may attend a permitted Anchalika/Zilla event outside the person's own Anchalika/Zilla.

This is event participation only.

It does not change:

* Membership
* Current Sakha
* Anchalika
* Zilla
* Sevak association

Therefore:

```text
Cross-Area Attendance
        ≠
Organizational Transfer
```

---

# 32. Seva Relationship

Seva is a separate lifecycle from Sevak participation.

Conceptually:

```text
Sevak Participation
       │
       └──────► Seva Assignment(s)
```

A Sevak may have multiple Seva Assignments.

Seva Assignment status is independent of Sevak status.

---

# 33. Seva After Inactivation

When a Sevak becomes INACTIVE:

```text
Sevak
ACTIVE → INACTIVE
```

existing Seva Assignments are not automatically terminated.

They are individually reviewed by the applicable Seva authority.

Possible result:

```text
Continue
```

or:

```text
End / Inactive
```

Detailed rules are maintained in:

```text
seva/01_seva_business_rules.md
seva/02_upbs_seva_rules.md
```

---

# 34. Seva After Transfer

Membership Transfer changes current Sakha.

It does not silently transfer Sakha-specific Seva assignments.

The lifecycle is:

```text
Membership Transfer
        ↓
Old Sakha Seva
        ↓
Historical
        ↓
New Sakha
        ↓
Fresh Seva Request / Recommendation
        ↓
Normal Approval
        ↓
New Assignment
```

UPBS Seva follows its separate Kendra review rules.

---

# 35. Training and Development

The earlier lifecycle model contained:

```text
Orientation
    ↓
Training
    ↓
Volunteer Development
    ↓
Seva
    ↓
Leadership
```

This remains a **conceptual organizational model**, not a mandatory technical lifecycle.

No mandatory training hierarchy is currently frozen.

There is no required:

```text
Orientation
→ Basic
→ Advanced
→ Leadership
```

progression.

---

# 36. Orientation

Orientation may exist as an operational activity.

However:

* It is not a mandatory Sevak status.
* It is not a required lifecycle gate.
* Completion is not required to make a person ACTIVE under the current core rules.

Future orientation workflows shall be separately documented if required.

---

# 37. Training

Training may be provided through Sevak Sangha.

Possible areas may include:

* Sadachara
* Seva
* Volunteer development
* UPBS volunteer preparation
* Leadership development

However, the exact sequence, levels and mandatory requirements remain outside the frozen Sevak lifecycle.

---

# 38. Volunteer Development

Volunteer development is an organizational objective of Sevak Sangha.

It is not a separate Sevak participation status.

Therefore:

```text
Volunteer Development
        ≠
ACTIVE / INACTIVE Status
```

---

# 39. Leadership Development

Leadership development is also an organizational objective.

It does not automatically create a governance position.

A future governance/position assignment must follow the common Governance framework.

---

# 40. UPBS Volunteer Pathway

The earlier conceptual lifecycle identified a possible:

```text
Sevak Sangha
    ↓
UPBS Volunteer Training
    ↓
UPBS Volunteer
```

pathway.

This is not an automatic lifecycle transition.

UPBS registration and operational rules remain owned by the UPBS module.

---

# 41. Kishor → Sevak Pathway

A possible pathway may exist:

```text
Kishor
   ↓
Sevak Sangha
```

but this is not an automatic lifecycle transition.

Any such transition must follow the applicable Membership and Sevak eligibility rules.

No automatic conversion is created by this document.

---

# 42. Governance Pathway

The earlier conceptual lifecycle contained:

```text
Eligible
   ↓
Sevak Sangha Executive
   ↓
Position Assignment
```

This remains subject to the pending Sevak governance framework.

The current document does not freeze:

* Executive positions
* Selection/Election
* Term duration
* Office hierarchy

Where such governance is implemented, it must use the common NSS Governance framework.

---

# 43. Lifecycle and Membership Status

Sevak status must not duplicate NSS Membership status.

Example:

```text
Membership Status = REGULAR_MEMBER
Sevak Status = ACTIVE
```

or:

```text
Membership Status = REGULAR_MEMBER
Sevak Status = INACTIVE
```

The two statuses serve different purposes.

---

# 44. Lifecycle and Sangha Sevi ID

The Sangha Sevi ID remains permanent.

Sevak inactivation or reactivation does not create a new Sangha Sevi ID.

Membership Transfer also does not create a new Sangha Sevi ID.

Therefore:

```text
Person
    ↓
One Sangha Sevi ID
    ↓
Sevak Participation History
```

---

# 45. Lifecycle History

The ERP shall preserve:

* First Sevak Enrollment Date
* Participation start date
* Participation status changes
* Inactivation reason
* Inactivation source
* Transfer-triggered changes
* Death-triggered changes
* Reactivation
* Reactivation review cycles
* Sakha association history
* Event participation
* Seva assignment history

Historical records shall never be physically deleted.

---

# 46. Lifecycle Event Sources

Sevak lifecycle changes may originate from:

```text
SEVAK_ENROLLMENT
```

```text
MEMBERSHIP_TRANSFER
```

```text
PERSON_DEATH
```

```text
MANUAL_INACTIVATION
```

```text
REACTIVATION_REVIEW
```

The source of each status change shall be auditable.

---

# 47. Lifecycle Transition Matrix

| Current State          | Trigger                 | Result                            | Source            |
| ---------------------- | ----------------------- | --------------------------------- | ----------------- |
| No Sevak Participation | Authorized enrollment   | ACTIVE                            | MANUAL            |
| ACTIVE                 | Manual inactivation     | INACTIVE                          | MANUAL            |
| ACTIVE                 | Membership Transfer     | INACTIVE                          | SYSTEM            |
| ACTIVE                 | Person Death            | INACTIVE                          | SYSTEM            |
| INACTIVE               | Authorized reactivation | ACTIVE                            | MANUAL            |
| INACTIVE               | Attendance              | INACTIVE                          | No status change  |
| INACTIVE               | Attendance + review     | ACTIVE or INACTIVE                | AUTHORIZED REVIEW |
| INACTIVE               | Membership Transfer     | Historical / new Sakha evaluation | SYSTEM            |
| INACTIVE               | Death                   | INACTIVE                          | SYSTEM            |

---

# 48. Lifecycle Transition Rules

The following transitions are prohibited:

```text
INACTIVE
   ↓
ATTENDANCE
   ↓
AUTOMATIC ACTIVE
```

and:

```text
ACTIVE
   ↓
MISSED ATTENDANCE
   ↓
AUTOMATIC INACTIVE
```

and:

```text
MEMBERSHIP TRANSFER
   ↓
MANUAL SEVAK TRANSFER
```

The Membership lifecycle is authoritative for transfer.

---

# 49. Administrative Authority

Sevak lifecycle actions use the centralized NSS ERP RBAC.

Authorized users may perform applicable:

* Enrollment
* Manual inactivation
* Reactivation review
* Reactivation
* Lifecycle corrections

System-generated transfer/death transitions do not require manual intervention.

Specific role/office-bearer permissions are governed by the Administration/RBAC module.

---

# 50. Audit Requirements

Every lifecycle transition must be auditable.

At minimum:

```text
Person / Membership
Action
Previous State
New State
Source
Reason
Changed By
Changed At
Related Lifecycle Event
```

For system-generated transitions:

```text
Source = SYSTEM
```

and the triggering lifecycle event shall be traceable.

---

# 51. Historical Integrity

The lifecycle must preserve historical truth.

The ERP shall never rewrite historical participation simply because the current state changed.

Example:

```text
2020
ACTIVE

2024
INACTIVE

2025
ACTIVE

2026
TRANSFERRED
```

All states remain historically traceable.

---

# 52. No Physical Deletion

The following shall not be physically deleted:

* Sevak participation
* Status history
* Enrollment history
* Sakha association history
* Transfer history
* Death-triggered inactivation history
* Reactivation review history
* Event participation history
* Seva assignment history

Retirement/inactivation is represented through lifecycle status and history.

---

# 53. Lifecycle Summary

The authoritative current lifecycle is:

```text
                 NSS MEMBERSHIP
                       │
                       ▼
                  ELIGIBILITY
                       │
                       ▼
                  ENROLLMENT
                       │
                       ▼
                    ACTIVE
                       │
          ┌────────────┼─────────────┐
          │            │             │
          ▼            ▼             ▼
     MANUAL INACTIVE  TRANSFER      DEATH
          │            │             │
          │            ▼             ▼
          │        OLD INACTIVE   INACTIVE
          │            │
          │            ▼
          │       NEW SAKHA CHECK
          │            │
          │       ┌────┴────┐
          │       ▼         ▼
          │    HAS SEVAK   NO SEVAK
          │       │         │
          │       ▼         ▼
          │     ACTIVE    NO CURRENT
          │               PARTICIPATION
          │
          ▼
       INACTIVE
          │
          ▼
   ELIGIBLE EVENT
    PARTICIPATION
          │
          ▼
 REACTIVATION REVIEW
          │
      ┌───┴────┐
      ▼        ▼
    ACTIVE   INACTIVE
```

---

# 54. Frozen Lifecycle Principles

The following lifecycle principles are frozen:

* NSS Membership is mandatory for Sevak participation.
* Sevak does not create a separate NSS Membership.
* Sangha Sevi ID remains authoritative.
* Sevak participation has only ACTIVE and INACTIVE states.
* Direct enrollment is permitted for eligible NSS Members.
* First Sevak Enrollment Date is permanent.
* No additional Sevak-specific age restriction is defined.
* No attendance-based automatic inactivity exists.
* Manual inactivation requires a reason.
* Transfer-triggered inactivation is automatic.
* Death-triggered inactivation is automatic.
* Transfer follows NSS Membership Sakha.
* There is no independent Sevak transfer workflow.
* A Sakha may or may not have a Sevak Sangha.
* No current local Sevak participation exists where the current Sakha has no Sevak Sangha.
* Historical Sevak participation is preserved.
* INACTIVE does not automatically prohibit permitted event participation.
* INACTIVE attendance does not automatically reactivate.
* INACTIVE attendance may create a reactivation review.
* Only one open reactivation review may exist per Sevak.
* Reactivation requires authorized human action.
* Reactivation does not require a reason.
* Death is a global Person/Membership lifecycle event.
* Death-triggered Sevak inactivation requires no manual intervention.
* A deceased person cannot be normally reactivated as a Sevak.
* Event participation and Sevak status remain separate.
* Seva Assignment and Sevak status remain separate.
* Multiple Seva Assignments may exist.
* No mandatory training hierarchy is frozen.
* Orientation and training are not lifecycle status gates.
* UPBS Volunteer pathway is not automatic.
* Kishor → Sevak transition is not automatic.
* Sevak governance pathway remains subject to pending governance rules.
* Historical records are never physically deleted.
* All lifecycle transitions are auditable.

---

# 55. Related Documents

```text
01_sevak_module_overview.md
02_sevak_erd.md
04_sevak_participation_rules.md
05_sevak_business_rules.md
06_sevak_table_design.md

sangha/
├── 01_sakha_sevak_sangha_session_rules.md
└── 02_anchalika_zilla_sevak_sangha_puja_rules.md

seva/
├── 01_seva_business_rules.md
└── 02_upbs_seva_rules.md

events/
└── 01_other_sevak_event_rules.md
```

Related core modules:

```text
Membership
Person
Attendance
Administration / RBAC
Governance
UPBS
Reports
```

---

# End of Document
