# NSS ERP — Kumari Sangha Lifecycle

**Document ID:** SOL-KUM-003  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kumari Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle of a Kumari Sangha participant from initial identification through active participation, development activities, possible transition to NSS Membership, or closure of Kumari participation.

The lifecycle preserves the distinction between:

```text
Kumari Participation
        ≠
NSS Membership
```

and:

```text
Kumari ID
        ≠
Sangha Sevi ID
```

These identity and transition rules are frozen in the existing Kumari source.

---

# 2. Lifecycle Overview

The overall lifecycle is:

```text
Person Identified
      ↓
Kumari Eligibility
      ↓
Kumari Enrollment
      ↓
Kumari ID Generated
      ↓
ACTIVE Kumari
      ↓
Activities / Training / Development
      │
      ├───────────────┐
      │               │
      ▼               ▼
NSS Membership     Exit / Closure
Application            │
      │                ├── MARRIED_OUT
      ▼                ├── WITHDRAWN
Membership             └── DECEASED
Approved
      │
      ▼
Sangha Sevi ID
      │
      ▼
Kumari Status =
BECAME_NSS_MEMBER
```

---

# 3. Person Foundation

The lifecycle begins with a Person record.

```text
PERSON
   ↓
Potential Kumari Participant
```

The Person record is owned by the Person module.

Kumari does not create a duplicate Person record.

---

# 4. Eligibility

A person may enter the Kumari lifecycle when she satisfies the applicable Kumari eligibility requirements.

The current project source identifies the intended population as:

```text
Young Girls
Daughters of NSS Families
Adolescent Age Group
```

The exact age boundary is not currently frozen in the available source.

Therefore:

```text
Exact Age Limit = PENDING
```

No unsupported age cutoff shall be hard-coded.

---

# 5. Kumari Enrollment

After eligibility is established:

```text
Eligible Girl
      ↓
Kumari Enrollment
      ↓
Kumari Membership Record
```

The enrollment establishes participation in Kumari Sangha.

It does not create NSS Membership.

---

# 6. Kumari Identity Creation

At enrollment, the participant receives a Kumari ID.

Example:

```text
KM000001
KM000002
KM000003
```

The Kumari ID is:

```text
Unique
Permanent
Never Reused
Valid within Kumari Sangha
```

The existing frozen source explicitly establishes this identity model.

---

# 7. Identity State

After enrollment:

```text
Person
  ↓
Kumari Membership
  ↓
KM000123
```

The participant's Kumari history is now independently traceable.

---

# 8. ACTIVE State

The normal active lifecycle state is:

```text
ACTIVE
```

An ACTIVE Kumari may participate in applicable:

* Kumari activities
* Training
* Dina-Lipi
* Niyam Panchak
* Dasa Sheela
* Other approved development activities

---

# 9. Active Participation

The active participant may have:

```text
Kumari Membership
        │
        ├── Activities
        ├── Training
        ├── Dina-Lipi
        ├── Niyam Panchak
        └── Dasa Sheela
```

Participation history shall remain associated with the Kumari identity.

---

# 10. Activity Lifecycle

A Kumari activity follows the common activity/event lifecycle where applicable.

Conceptually:

```text
Activity Created
      ↓
Activity Available
      ↓
Kumari Participation
      ↓
Activity Completed
      ↓
Participation History Preserved
```

The activity itself does not change Kumari membership status.

---

# 11. Training Lifecycle

Training is part of the Kumari development program.

Conceptually:

```text
Training Available
      ↓
Kumari Participates
      ↓
Training History Recorded
      ↓
Development Progress Preserved
```

Detailed training assessment/certification rules are not currently frozen.

---

# 12. Dina-Lipi Lifecycle

Dina-Lipi is a core Kumari development activity.

At lifecycle level:

```text
Kumari
   ↓
Dina-Lipi Participation
   ↓
Progress / History
```

Detailed scoring or assessment rules remain outside this lifecycle document unless later approved.

---

# 13. Niyam Panchak Lifecycle

Niyam Panchak forms part of the Kumari development program.

Conceptually:

```text
Kumari
   ↓
Niyam Panchak Learning
   ↓
Participation / Progress History
```

No unsupported completion or certification state is introduced.

---

# 14. Dasa Sheela Lifecycle

Dasa Sheela forms part of the Kumari development program.

Conceptually:

```text
Kumari
   ↓
Dasa Sheela Learning
   ↓
Participation / Progress History
```

Detailed assessment rules remain pending unless separately approved.

---

# 15. Family Relationship During Active State

An ACTIVE Kumari may remain connected to her NSS family through the common Family module.

Conceptually:

```text
Family
  │
  └── Daughter
        │
        ▼
     Kumari
     KM000123
```

Family relationships remain owned by the Family module.

---

# 16. NSS Membership Boundary

Being an ACTIVE Kumari does not automatically create NSS Membership.

Therefore:

```text
ACTIVE KUMARI
      ≠
NSS MEMBER
```

and:

```text
KM000123
      ≠
SS000123
```

The existing frozen identity model explicitly establishes this separation.

---

# 17. NSS Membership Application

An ACTIVE Kumari may later apply for NSS Membership.

The lifecycle becomes:

```text
ACTIVE KUMARI
      ↓
Interested / Eligible
      ↓
NSS Membership Application
      ↓
Membership Review
```

Application and approval are governed by the common NSS Membership framework.

---

# 18. Membership Review

The membership authority may consider the participant's Kumari history.

The existing source identifies considerations such as:

* Years of Kumari participation
* Dina-Lipi participation
* Niyam Panchak knowledge
* Dasa Sheela knowledge
* Conduct and discipline
* Seva participation
* Recommendation

These are assessment considerations, not automatic membership approval.

---

# 19. Membership Type Decision

A long-term active Kumari participant may be considered for:

```text
Regular Membership
```

directly, where the applicable authority approves.

Alternatively:

```text
Probationary Membership
```

may be granted.

Therefore:

```text
Kumari Participation
        ↓
Membership Application
        ↓
Membership Decision
        ├── Regular
        └── Probationary
```

Probationary Membership is not automatically mandatory for every Kumari participant.

---

# 20. NSS Membership Approval

After NSS Membership approval:

```text
Membership Approved
      ↓
Sangha Sevi Record
      ↓
Sangha Sevi ID Generated
```

Example:

```text
KM000123
      ↓
Approved NSS Membership
      ↓
SS000456
```

---

# 21. Sangha Sevi ID Creation

The Sangha Sevi ID is generated only after approved NSS Membership.

The Kumari participant does not consume an NSS Membership ID merely by joining Kumari Sangha.

This preserves the distinction between:

```text
KM000123
```

and:

```text
SS000456
```

---

# 22. Identity Link Preservation

After transition:

```text
KM000123
      │
      └──── linked to ────► SS000456
```

Both identities remain historically preserved.

The original Kumari identity is never reused.

---

# 23. Transition Record

The transition shall create a:

```text
kumari_membership_transition
```

record.

Conceptually:

```text
Kumari Membership
      ↓
Transition Record
      ↓
Sangha Sevi
```

The frozen source identifies the transition information as including:

```text
transition_pk
kumari_membership_pk
sangha_sevi_pk
transition_date
membership_type_granted
remarks
```

---

# 24. BECAME_NSS_MEMBER State

After successful NSS Membership transition:

```text
Kumari Status
=
BECAME_NSS_MEMBER
```

This status records the reason for the end of active Kumari participation.

It does not mean the historical Kumari record is deleted.

---

# 25. Direct Membership Transition

A Kumari may transition to NSS Membership without marriage.

Example:

```text
KM000123
      ↓
Active Kumari
      ↓
NSS Membership Application
      ↓
Approved
      ↓
SS000456
      ↓
Kumari Status =
BECAME_NSS_MEMBER
```

This scenario is explicitly supported by the frozen transition model.

---

# 26. Marriage Transition

The current frozen Kumari rule states that only unmarried girls remain active members of Kumari Sangha.

After marriage:

```text
ACTIVE
   ↓
Marriage
   ↓
MARRIED_OUT
```

The Kumari participation therefore leaves its active state.

---

# 27. Marriage and Family History

Marriage does not erase the Kumari participant's birth-family history.

After marriage:

```text
Kumari Participant
      ↓
Marriage Relationship
      ↓
MARRIED_OUT
```

The marriage relationship is recorded through the common Family module.

The source explicitly preserves the Kumari participant within her birth-family history.

---

# 28. Non-NSS Spouse

A spouse does not need to be an NSS member to exist in the Person/Family model.

Therefore:

```text
Spouse
   ↓
Person
   ↓
Family Relationship
```

may exist without:

```text
Sangha Sevi ID
Membership
```

---

# 29. Later Membership After Marriage

A former Kumari participant may later apply for NSS Membership where eligible.

Example:

```text
KM000123
      ↓
Marriage
      ↓
MARRIED_OUT
      ↓
Later NSS Membership Application
      ↓
SS000456
```

The Kumari history remains preserved.

---

# 30. WITHDRAWN State

A Kumari may leave the program voluntarily.

Lifecycle:

```text
ACTIVE
   ↓
Withdrawal
   ↓
WITHDRAWN
```

The withdrawal shall not delete:

* Kumari ID
* Previous activities
* Training history
* Dina-Lipi history
* Other participation records

---

# 31. DECEASED State

Where the Person is deceased:

```text
ACTIVE
   ↓
Death
   ↓
DECEASED
```

The Person lifecycle remains owned by the Person module.

The Kumari record becomes historical.

---

# 32. Explicit Kumari Exit States

The frozen Kumari model uses explicit reasons rather than a generic INACTIVE state.

The documented states/reasons are:

```text
ACTIVE

MARRIED_OUT

BECAME_NSS_MEMBER

WITHDRAWN

DECEASED
```

This preserves the actual reason for leaving active Kumari participation.

---

# 33. State Transition Matrix

| Current State | Event                   | Next State        |
| ------------- | ----------------------- | ----------------- |
| Eligible      | Enrollment              | ACTIVE            |
| ACTIVE        | Approved NSS Membership | BECAME_NSS_MEMBER |
| ACTIVE        | Marriage                | MARRIED_OUT       |
| ACTIVE        | Voluntary withdrawal    | WITHDRAWN         |
| ACTIVE        | Death                   | DECEASED          |

The transition to NSS Membership is subject to the common Membership approval process.

---

# 34. Invalid State Transitions

The system shall not automatically:

```text
MARRIED_OUT → ACTIVE
WITHDRAWN → ACTIVE
DECEASED → ACTIVE
BECAME_NSS_MEMBER → ACTIVE
```

without an explicitly approved business rule.

No automatic reactivation rule is currently frozen.

---

# 35. Historical Preservation

Every lifecycle transition shall preserve:

```text
Previous State
New State
Effective Date
Reason
Authority / Source
Audit Information
```

where applicable under the common audit standards.

---

# 36. No Physical Deletion

A Kumari participant shall not be physically deleted merely because participation ends.

The system must preserve:

```text
Kumari ID
Person
Membership History
Activity History
Training History
Transition History
Exit History
```

---

# 37. Lifecycle and Activities

Activities do not independently terminate the Kumari lifecycle.

For example:

```text
Activity Completed
      ↓
Kumari remains ACTIVE
```

unless a separate lifecycle event occurs.

---

# 38. Lifecycle and Training

Completion of training does not automatically create NSS Membership.

Therefore:

```text
Training Completed
      ≠
NSS Membership
```

Training history may nevertheless contribute to later membership assessment.

---

# 39. Lifecycle and Dina-Lipi

Dina-Lipi participation does not automatically change membership status.

It remains part of the development history.

---

# 40. Lifecycle and Niyam Panchak

Niyam Panchak participation does not automatically change membership status.

It remains part of the development history.

---

# 41. Lifecycle and Dasa Sheela

Dasa Sheela participation does not automatically change membership status.

It remains part of the development history.

---

# 42. Lifecycle and Mahila Sangha

Kumari Sangha may function as a developmental pathway toward future Mahila Sangha participation.

Conceptually:

```text
Kumari Sangha
      ↓
Development
      ↓
Future Eligibility
      ↓
Mahila Sangha
```

This is not an automatic membership conversion.

The future Mahila relationship must follow the applicable Mahila/NSS membership rules.

---

# 43. Lifecycle and Family

Family changes do not automatically change the Kumari ID.

For example:

```text
Marriage
   ↓
Family Relationship Changes
   ↓
Kumari Status = MARRIED_OUT
```

The original Kumari identity remains preserved.

---

# 44. Lifecycle and Organization

If the participant's associated Sakha or organizational context changes, the common Organization lifecycle shall preserve the organizational relationship.

A change of organizational association does not create a new Kumari ID.

---

# 45. Kumari ID Permanence

The Kumari ID remains permanently associated with the historical Kumari participation.

Example:

```text
KM000123

ACTIVE
   ↓
MARRIED_OUT
```

or:

```text
KM000123

ACTIVE
   ↓
BECAME_NSS_MEMBER
```

The ID remains:

```text
KM000123
```

throughout the historical record.

---

# 46. NSS ID Permanence

After NSS Membership approval:

```text
SS000456
```

is generated according to the common NSS Membership identity rules.

The Sangha Sevi ID is separate from the Kumari ID.

---

# 47. Complete Lifecycle Example — Direct NSS Transition

```text
Person
  ↓
Eligible Kumari
  ↓
Enrollment
  ↓
KM000123
  ↓
ACTIVE
  │
  ├── Dina-Lipi
  ├── Training
  ├── Niyam Panchak
  └── Dasa Sheela
  ↓
NSS Membership Application
  ↓
Membership Review
  ↓
Regular Membership Approved
  ↓
SS000456
  ↓
Kumari Status =
BECAME_NSS_MEMBER
```

---

# 48. Complete Lifecycle Example — Marriage

```text
Person
  ↓
Kumari Enrollment
  ↓
KM000123
  ↓
ACTIVE
  ↓
Marriage
  ↓
MARRIED_OUT
  ↓
Family Relationship Updated
  ↓
Kumari History Preserved
```

---

# 49. Complete Lifecycle Example — Withdrawal

```text
KM000123
   ↓
ACTIVE
   ↓
Voluntary Withdrawal
   ↓
WITHDRAWN
   ↓
Historical Records Preserved
```

---

# 50. Complete Lifecycle Example — Death

```text
KM000123
   ↓
ACTIVE
   ↓
Person Deceased
   ↓
DECEASED
   ↓
Historical Records Preserved
```

---

# 51. Complete Lifecycle Example — Marriage Then NSS Membership

```text
KM000123
   ↓
ACTIVE
   ↓
Marriage
   ↓
MARRIED_OUT
   ↓
Later NSS Membership Application
   ↓
Membership Approved
   ↓
SS000456
   ↓
Kumari History Linked to NSS History
```

The Family module preserves the marriage and family transition history.

---

# 52. Lifecycle Audit

The following actions shall be auditable:

```text
Kumari Enrollment
Kumari ID Generation
Status Change
Marriage Transition
Withdrawal
Death
NSS Membership Application
Membership Approval
Kumari → NSS Transition
Activity Participation
Training Participation
Administrative Corrections
```

---

# 53. Lifecycle Ownership

| Lifecycle Area       | Owner          |
| -------------------- | -------------- |
| Person               | Person         |
| Family / Marriage    | Family         |
| Kumari Participation | Kumari         |
| Kumari Activities    | Kumari / Event |
| NSS Membership       | Membership     |
| Sangha Sevi ID       | Membership     |
| Governance           | Governance     |
| Attendance           | Attendance     |
| Audit                | Audit          |

---

# 54. Lifecycle Boundary

The Kumari module owns:

```text
Kumari Identity
Kumari Participation
Kumari Status
Kumari Activities
Kumari Transition History
```

It does not own:

```text
Person Identity
Family Identity
Marriage
NSS Membership
Sangha Sevi Identity
Governance
Finance
Audit Infrastructure
```

---

# 55. Final Lifecycle Model

```text
                         PERSON
                           │
                           ▼
                    KUMARI ELIGIBILITY
                           │
                           ▼
                      ENROLLMENT
                           │
                           ▼
                     KUMARI ID
                     KM000123
                           │
                           ▼
                        ACTIVE
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
         ACTIVITIES     TRAINING      DEVELOPMENT
             │
             │
             ├───────────────┐
             │               │
             ▼               ▼
        NSS MEMBERSHIP      MARRIAGE
          APPLICATION          │
             │                 ▼
             ▼            MARRIED_OUT
          APPROVAL
             │
             ▼
        SANGHA SEVI ID
          SS000456
             │
             ▼
     BECAME_NSS_MEMBER


ACTIVE
  │
  ├── Withdrawal → WITHDRAWN
  │
  └── Death → DECEASED
```

---

# 56. Core Lifecycle Principles

The Kumari lifecycle is governed by these principles:

```text
1. Kumari has its own identity.

2. Kumari ID is separate from Sangha Sevi ID.

3. Kumari participation does not automatically create NSS Membership.

4. NSS Membership requires its own approval.

5. Long-term Kumari participation may support consideration for direct Regular Membership.

6. The original Kumari ID is never reused.

7. Kumari history is never deleted.

8. Marriage creates an explicit MARRIED_OUT state.

9. Withdrawal creates an explicit WITHDRAWN state.

10. Death creates an explicit DECEASED state.

11. NSS transition creates an explicit BECAME_NSS_MEMBER state.

12. Family and marriage history remain owned by the Family module.

13. The Kumari → NSS relationship is permanently traceable.
```

---

# 57. Source-Aligned Decisions

The following are directly based on the existing frozen Kumari source:

```text
✓ KM identity
✓ Permanent / never-reused Kumari ID
✓ Separate NSS Membership identity
✓ NSS ID generated after membership approval
✓ Kumari → NSS transition history
✓ MARRIED_OUT
✓ BECAME_NSS_MEMBER
✓ WITHDRAWN
✓ DECEASED
✓ Marriage/family history preservation
✓ Long-term participant membership consideration
```

---

# 58. Pending Lifecycle Rules

The following are not sufficiently frozen in the available source:

```text
Exact Kumari age limit
Detailed enrollment approval workflow
Detailed training completion lifecycle
Dina-Lipi assessment lifecycle
Niyam Panchak assessment lifecycle
Dasa Sheela assessment lifecycle
Detailed reactivation policy
Detailed organizational transfer workflow
```

These shall remain pending rather than being invented.

---

# 59. Related Documents

```text
01_kumari_module_overview.md
02_kumari_erd.md
03_kumari_lifecycle.md
04_kumari_business_rules.md
05_kumari_table_design.md
```

Related common modules:

```text
Person
Family
Membership
Organization
Governance
Event
Attendance
Audit
Administration
```

---

# 60. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

The lifecycle preserves the frozen distinction:

```text
KM000123
    ≠
SS000456
```

while maintaining a permanent historical relationship between the two identities when the Kumari later becomes an NSS member.

---

# End of Document
