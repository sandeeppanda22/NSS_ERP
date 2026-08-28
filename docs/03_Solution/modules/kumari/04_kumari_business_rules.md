# NSS ERP — Kumari Sangha Business Rules

**Document ID:** SOL-KUM-004  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kumari Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing Kumari Sangha participation within NSS ERP.

The rules cover:

- Kumari identity
- Kumari participation
- Status
- Enrollment
- Activities
- Training
- Dina-Lipi
- Niyam Panchak
- Dasa Sheela
- Family integration
- Marriage
- Withdrawal
- Death
- NSS Membership transition
- Identity preservation
- Visibility
- History and audit

This document does not define PostgreSQL SQL or implementation code.

---

# 2. Governing Principles

The Kumari module follows:

1. Person and Membership are separate concepts.
2. Kumari participation is separate from NSS Membership.
3. Kumari ID is separate from Sangha Sevi ID.
4. Kumari history is permanent.
5. A Kumari ID is never reused.
6. NSS Membership requires its own approval.
7. Family relationships are owned by the Family module.
8. Common NSS architecture shall be reused where applicable.
9. Historical records shall not be physically deleted.

---

# 3. KUM-001 — Kumari Identity

Every Kumari participant shall receive a unique Kumari ID.

Example:

```text
KM000001
KM000002
KM000003
```

The Kumari ID identifies the participant within the Kumari Sangha domain.

---

# 4. KUM-002 — Kumari ID Permanence

A Kumari ID shall be:

* Unique
* Permanent
* Never reused

Ending Kumari participation shall not release the ID for future use.

---

# 5. KUM-003 — Kumari ID and Sangha Sevi ID Are Different

The following are separate identities:

```text
Kumari ID
KM000123

Sangha Sevi ID
SS000456
```

A Kumari participant does not automatically receive an NSS Sangha Sevi ID.

The frozen project source explicitly establishes this distinction.

---

# 6. KUM-004 — NSS Membership Is Separate

Kumari Sangha participation shall not be treated as an NSS Membership category.

Therefore:

```text
Kumari Participant
        ≠
NSS Member
```

A Kumari may participate without having an NSS Membership record.

---

# 7. KUM-005 — Person Foundation

Every Kumari participant shall be associated with a Person record.

The Kumari module shall not create a duplicate Person record.

---

# 8. KUM-006 — Family Integration

Where applicable, a Kumari participant shall be associated with the common Family module.

Family relationships shall be maintained by the Family module.

The Kumari module shall not duplicate:

* Family
* Parent
* Spouse
* Family relationship
* Marriage records

---

# 9. KUM-007 — Eligibility

The current project source identifies the intended Kumari population as:

* Young girls
* Daughters of NSS families
* Adolescent age group

The exact age boundary is not currently frozen.

Therefore the ERP shall not hard-code an unsupported age limit.

---

# 10. KUM-008 — Enrollment

An eligible participant may be enrolled in Kumari Sangha.

Enrollment creates the Kumari participation record and Kumari identity.

```text
Eligible Person
      ↓
Kumari Enrollment
      ↓
Kumari Membership
      ↓
KM ID
```

---

# 11. KUM-009 — No Automatic NSS Membership

Kumari enrollment shall never automatically create NSS Membership.

The following is invalid:

```text
Kumari Enrollment
      ↓
Automatic Sangha Sevi ID
```

Instead:

```text
Kumari
      ↓
Later NSS Membership Application
      ↓
Approval
      ↓
Sangha Sevi ID
```

---

# 12. KUM-010 — Active Status

An actively participating Kumari shall have:

```text
ACTIVE
```

status.

ACTIVE indicates current Kumari participation.

It does not mean:

* NSS Membership
* Regular Membership
* Probationary Membership
* Mandatory activity attendance

---

# 13. KUM-011 — Kumari End Reasons

The frozen Kumari model defines:

```text
ACTIVE
MARRIED_OUT
BECAME_NSS_MEMBER
WITHDRAWN
DECEASED
```

These states/reasons preserve why active Kumari participation ended.

---

# 14. KUM-012 — Marriage Rule

Only unmarried girls may remain active members of Kumari Sangha.

After marriage:

```text
Kumari Status
=
MARRIED_OUT
```

The Kumari participation shall not continue as active.

The frozen source explicitly establishes this rule.

---

# 15. KUM-013 — Marriage Does Not Delete History

Marriage shall never delete the participant's Kumari history.

The system shall retain:

* Kumari ID
* Enrollment history
* Activity history
* Training history
* Participation history
* Previous status
* Marriage-related transition

---

# 16. KUM-014 — Marriage Is a Family Event

The marriage relationship shall be recorded through the common Family module.

Kumari shall only reflect the resulting participation status:

```text
MARRIED_OUT
```

---

# 17. KUM-015 — Spouse Does Not Automatically Become Member

Marriage to a person does not automatically create NSS Membership for the spouse.

The spouse shall have an independent Person record.

Membership shall follow the normal NSS Membership process.

---

# 18. KUM-016 — Withdrawal

A Kumari may voluntarily withdraw from Kumari participation.

The status becomes:

```text
WITHDRAWN
```

The withdrawal shall not delete historical information.

---

# 19. KUM-017 — Death

When the Person is recorded as deceased, the Kumari participation shall become:

```text
DECEASED
```

The death event is owned by the common Person lifecycle.

---

# 20. KUM-018 — Death Is a Global Lifecycle Event

The Kumari module shall not independently determine death.

It shall respond to the authoritative Person lifecycle.

```text
Person
  ↓
DECEASED
  ↓
Kumari Participation
  ↓
DECEASED
```

---

# 21. KUM-019 — No Automatic Inactivation From Attendance

Kumari participation shall not automatically become inactive merely because a participant misses activities.

No attendance threshold is currently frozen.

---

# 22. KUM-020 — Activity Participation

A Kumari may participate in multiple activities.

Participation shall be recorded separately from Kumari membership.

```text
Kumari Membership
        ↓
Activity Participation
        ↓
Kumari Activity
```

---

# 23. KUM-021 — Activity Does Not Change Membership

Participation in an activity shall not automatically change Kumari status.

For example:

```text
Training Completed
      ≠
NSS Membership
```

and:

```text
Activity Missed
      ≠
Kumari Terminated
```

---

# 24. KUM-022 — Dina-Lipi

Dina-Lipi is a core Kumari development activity.

The ERP shall support recording Dina-Lipi participation/progress where the applicable operational workflow is defined.

No unsupported scoring system shall be introduced.

---

# 25. KUM-023 — Niyam Panchak

Niyam Panchak is part of Kumari development.

The ERP shall support its participation/training context.

Detailed assessment or certification rules remain pending authoritative definition.

---

# 26. KUM-024 — Dasa Sheela

Dasa Sheela is part of Kumari development.

The ERP shall support its participation/training context.

Detailed assessment or certification rules remain pending authoritative definition.

---

# 27. KUM-025 — Training

Training may be conducted as part of Kumari Sangha development.

Training history shall be preserved.

Training completion does not automatically create NSS Membership.

---

# 28. KUM-026 — Development History

The participant's development history may include:

```text
Dina-Lipi
Niyam Panchak
Dasa Sheela
Training
Activities
Service Participation
```

This history may later support membership assessment where applicable.

---

# 29. KUM-027 — Long-Term Participation

Long-term active Kumari participants may be considered for NSS Membership.

Participation history may be used during membership review.

The frozen project rule specifically recognizes long-term Kumari participation as relevant to membership consideration.

---

# 30. KUM-028 — Membership Application

A former or active Kumari participant may apply for NSS Membership where eligible.

The application shall be handled by the common Membership module.

---

# 31. KUM-029 — Membership Review

The reviewing authority may consider:

* Years of Kumari participation
* Dina-Lipi participation
* Niyam Panchak knowledge
* Dasa Sheela knowledge
* Conduct and discipline
* Seva participation
* Recommendation

These considerations come from the frozen Kumari transition rule.

---

# 32. KUM-030 — Membership Is Not Automatic

Even where a Kumari has participated for many years:

```text
Kumari History
      ≠
Automatic NSS Membership
```

Membership approval remains a separate governance decision.

---

# 33. KUM-031 — Direct Regular Membership Consideration

A long-term active Kumari participant may be considered for direct Regular Membership.

This is subject to approval by the applicable NSS Membership authority.

The project source explicitly states that Probationary Membership is not mandatory for every Kumari participant.

---

# 34. KUM-032 — Probationary Membership Consideration

Where the membership authority determines that Probationary Membership is appropriate, the applicant may be granted Probationary Membership.

Therefore the possible outcomes are:

```text
Kumari
   ↓
Membership Review
   ├── Regular Membership
   └── Probationary Membership
```

---

# 35. KUM-033 — Membership Authority Owns Decision

The Kumari module shall not approve NSS Membership.

The common Membership/Governance authority shall make the final membership decision.

---

# 36. KUM-034 — Sangha Sevi ID Generation

A Sangha Sevi ID shall be generated only after NSS Membership approval.

Example:

```text
KM000123
      ↓
Membership Approved
      ↓
SS000456
```

The original KM ID remains unchanged.

---

# 37. KUM-035 — Transition Record

Every successful Kumari → NSS transition shall preserve a transition record.

The logical transition record contains:

```text
transition_pk
kumari_membership_pk
sangha_sevi_pk
transition_date
membership_type_granted
remarks
```

This structure is frozen in the existing project source.

---

# 38. KUM-036 — Transition Status

After successful NSS Membership transition:

```text
Kumari Status
=
BECAME_NSS_MEMBER
```

This records why active Kumari participation ended.

---

# 39. KUM-037 — Permanent Identity Link

The relationship:

```text
KM000123
      ↓
SS000456
```

shall remain permanently traceable.

Neither identity replaces the other.

---

# 40. KUM-038 — Original Kumari History Preserved

After becoming an NSS member, the system shall retain the participant's complete Kumari history.

This includes:

* Kumari ID
* Enrollment
* Activities
* Training
* Development history
* Exit reason
* Transition record

---

# 41. KUM-039 — No Duplicate Membership

The transition shall not create a second Person.

The same Person remains associated with:

```text
Kumari History
+
NSS Membership
```

---

# 42. KUM-040 — Kumari and NSS Membership Status Are Independent

The following statuses are separate:

```text
Kumari Status
```

and:

```text
NSS Membership Status
```

Example:

```text
Kumari:
BECAME_NSS_MEMBER

NSS:
ACTIVE
```

These are valid simultaneously because they belong to different domains.

---

# 43. KUM-041 — Family Visibility

Authorized family members may view authorized Kumari information belonging to their own family.

Potential information includes:

* Participant details
* Registration details
* Activity history
* Training history
* Participation status
* Guardian/family information
* Membership transition status

The frozen visibility model explicitly limits family access to their own family records.

---

# 44. KUM-042 — Sakha Visibility

A Sakha-authorized user may view Kumari participants within the user's authorized Sakha scope.

The exact permission matrix remains controlled by the common RBAC module.

---

# 45. KUM-043 — Kendra Visibility

An authorized Kendra user may view Kumari participants across authorized Sakhas.

---

# 46. KUM-044 — Coordinator Visibility

Where Kumari/Mahila coordinators are assigned through the common Governance/RBAC framework, they may receive access to Kumari participants within their authorized scope.

No separate Kumari permission architecture shall be created.

---

# 47. KUM-045 — Organizational Scope

A Kumari's organizational association shall use the common Organization/Sakha model.

Changing organizational association shall not generate a new Kumari ID.

---

# 48. KUM-046 — Common Governance Model

If Kumari Sangha requires governance or coordinator assignments, the Unified Governance Model shall be used.

Common structures shall be reused rather than creating Kumari-specific governance tables.

---

# 49. KUM-047 — No Duplicate Family Tables

The Kumari module shall not create:

```text
kumari_family
kumari_parent
kumari_marriage
```

The common Family module owns these concepts.

---

# 50. KUM-048 — No Duplicate Person Table

The Kumari module shall not create:

```text
kumari_person
```

The common Person module is authoritative.

---

# 51. KUM-049 — No Duplicate NSS Membership Table

The Kumari module shall not create:

```text
kumari_nss_membership
```

The common Membership module is authoritative.

---

# 52. KUM-050 — No Duplicate Sangha Sevi Identity

The Kumari module shall not generate its own alternative NSS member identity.

The official NSS Membership identity remains the Sangha Sevi ID.

---

# 53. KUM-051 — History Never Deleted

Historical Kumari records shall not be physically deleted merely because participation ends.

The following shall remain available:

```text
Person
Kumari ID
Kumari Membership
Activities
Participation
Training
Transition
Exit History
```

---

# 54. KUM-052 — Auditability

The following actions shall be auditable:

* Kumari enrollment
* KM ID generation
* Status change
* Marriage status change
* Withdrawal
* Death-related status change
* Membership application
* Membership transition
* Activity participation
* Training records
* Administrative correction

---

# 55. KUM-053 — Status Change Audit

Every status change shall preserve, where applicable:

```text
Previous Status
New Status
Effective Date
Reason
Changed By
Changed At
```

---

# 56. KUM-054 — No Unsupported Age Rule

The ERP shall not enforce a specific age cutoff until an authoritative operational rule is documented.

Current source only establishes the intended demographic as young/adolescent girls.

---

# 57. KUM-055 — No Unsupported Assessment Rules

The ERP shall not invent:

* Dina-Lipi scores
* Niyam Panchak grading
* Dasa Sheela grading
* Training certification levels

unless approved requirements define them.

---

# 58. KUM-056 — Kumari vs Kishor

Kumari Sangha and Kishor Puja are separate business modules.

```text
Kumari Sangha
=
Continuous Development Program

Kishor Puja
=
Annual Event-Based Program
```

They shall not share a single business lifecycle merely because both are youth programs.

---

# 59. KUM-057 — Kumari vs Mahila

Kumari Sangha is not a Mahila membership category.

The relationship is developmental:

```text
Kumari
   ↓
Future Eligibility
   ↓
Mahila
```

Actual Mahila participation follows the applicable Mahila/NSS rules.

---

# 60. KUM-058 — Future Mahila Pipeline

Kumari Sangha may prepare participants for future Mahila Sangha participation through:

* Value education
* Training
* Discipline
* Seva
* Spiritual development
* Leadership development

This does not constitute automatic Mahila membership.

---

# 61. KUM-059 — Activity Participation Is Separate

The following concepts shall remain separate:

```text
Eligibility
Participation
Attendance
Membership
Status
```

One shall not automatically imply another unless a documented rule explicitly establishes that relationship.

---

# 62. KUM-060 — No Attendance-Based Termination

Absence from a Kumari activity shall not automatically terminate Kumari participation.

No attendance threshold is currently frozen.

---

# 63. KUM-061 — Activity History Is Permanent

Completed activities and participation records shall remain available for historical reporting.

---

# 64. KUM-062 — Transition History Is Permanent

A Kumari → NSS transition record shall never be overwritten or deleted.

---

# 65. KUM-063 — Multiple Activities

A Kumari may participate in multiple activities over the lifetime of her Kumari participation.

Each participation record remains independently traceable.

---

# 66. KUM-064 — Multiple Training Records

A Kumari may participate in multiple training programs.

Training history shall remain cumulative.

---

# 67. KUM-065 — No New KM ID on Activity

Participation in a new activity shall never generate a new Kumari ID.

The same KM ID remains the participant identity.

---

# 68. KUM-066 — No New KM ID on Organizational Change

Changing Sakha/organizational association shall not create a new Kumari ID.

---

# 69. KUM-067 — No New KM ID on Reactivation

If a future approved rule permits reactivation, the original KM ID shall be retained.

No new Kumari identity shall be generated.

---

# 70. KUM-068 — Reactivation Not Currently Frozen

No formal reactivation workflow is currently frozen.

Therefore the ERP shall not automatically support reactivation of:

```text
MARRIED_OUT
BECAME_NSS_MEMBER
WITHDRAWN
DECEASED
```

without an approved rule.

---

# 71. KUM-069 — Membership Transition Is One-Way by Default

The current frozen model treats:

```text
Kumari
    ↓
NSS Membership
```

as a historical transition.

There is no approved rule for:

```text
NSS Member
    ↓
Kumari Participant
```

---

# 72. KUM-070 — Membership Transition Does Not Erase Kumari History

After NSS Membership approval, Kumari records remain accessible for historical purposes.

---

# 73. KUM-071 — Membership Type Preserved

The transition record shall preserve the membership type granted:

```text
REGULAR_MEMBER
```

or:

```text
PROBATIONARY_MEMBER
```

as applicable.

---

# 74. KUM-072 — Recommendation Is Not Approval

A Kumari Sangha recommendation for NSS Membership shall not itself create membership.

The final membership authority must approve the application.

---

# 75. KUM-073 — Family Does Not Approve NSS Membership

Parents/guardians may participate in applicable family/consent workflows, but family visibility does not constitute NSS Membership approval.

---

# 76. KUM-074 — Role-Based Access

Access to Kumari records shall follow common NSS RBAC.

No Kumari-specific authentication mechanism shall be created.

---

# 77. KUM-075 — Audit and Correction

Historical Kumari information requiring correction shall follow the common ERP correction and audit framework.

Original values must remain traceable where correction workflows apply.

---

# 78. KUM-076 — Master Data

Kumari activity categories, status values, transition types and other configurable classifications should be master-data driven where applicable.

Hard-coded business categories shall be avoided unless explicitly frozen.

---

# 79. KUM-077 — Five Core Logical Entities

The current Kumari domain consists of:

```text
kumari_sangha
kumari_membership
kumari_activity
kumari_activity_participant
kumari_membership_transition
```

These remain the core logical entities.

---

# 80. KUM-078 — Common Architecture Reuse

The Kumari module shall reuse:

```text
Person
Family
Organization
Membership
Governance
Attendance
Audit
Administration/RBAC
Reports
```

where applicable.

---

# 81. KUM-079 — No SQL in Business Rules

This document defines business rules only.

It does not define:

* PostgreSQL DDL
* CREATE TABLE
* ALTER TABLE
* SQL constraints
* Django migrations

---

# 82. KUM-080 — Source Traceability

The rules in this document are derived from the existing frozen Kumari project source.

Particularly authoritative frozen decisions include:

```text
KM Identity
NSS Membership Identity
Membership End Reasons
Marriage Rule
Membership Transition
Long-Term Participant Membership Consideration
```

---

# 83. Final Kumari Lifecycle Rule

The final core lifecycle is:

```text
Eligible Girl
      ↓
Kumari Enrollment
      ↓
KM000123
      ↓
ACTIVE
      │
      ├── Activities
      ├── Training
      ├── Dina-Lipi
      ├── Niyam Panchak
      └── Dasa Sheela
      │
      ├───────────────┐
      │               │
      ▼               ▼
NSS Membership      Marriage
Application             │
      │                 ▼
      ▼            MARRIED_OUT
Membership
Approval
      │
      ▼
SS000456
      │
      ▼
BECAME_NSS_MEMBER

ACTIVE
   ├── Withdrawal → WITHDRAWN
   └── Death      → DECEASED
```

---

# 84. Final Identity Rule

```text
KM000123
    =
Permanent Kumari Identity

SS000456
    =
Permanent NSS Membership Identity
```

When the participant transitions:

```text
KM000123
      │
      └──────── permanently linked ────────►
                                             SS000456
```

---

# 85. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
