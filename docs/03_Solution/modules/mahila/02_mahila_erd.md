# NSS ERP — Mahila Sangha ERD

**Document ID:** SOL-MAH-002  
**Version:** 2.1.0  
**Status:** DRAFT — BYE-LAW ALIGNED  
**Module:** Mahila Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the conceptual Entity Relationship Model for the Mahila Sangha Module.

It establishes the relationships between:

- Person
- NSS Membership
- Mahila Sangha participation
- Mahila Sangha organizational context
- General Body
- Governing Body
- Office-bearer assignments
- Mahila activities
- Event participation
- Attendance
- Finance
- Audit
- Kendra Sangha relationship

This document defines the conceptual/domain model.

It does not freeze PostgreSQL implementation details.

Physical table design is defined separately in:

```text
05_mahila_table_design.md
```

---

# 2. Source Hierarchy

The conceptual model is derived from:

```text
Approved Mahila Sangha Bye-Law
        ↓
NSS Bye-Law
        ↓
Approved NSS Governance Framework
        ↓
Existing Mahila ERP Decisions
        ↓
Mahila Module Business Rules
```

Where a Mahila-specific Bye-Law provision exists, it is authoritative for that provision.

The approved Bye-Law establishes Nilachala Saraswata Mahila Sangha, its membership, General Body and Governing Body structure.

---

# 3. Core Identity Principle

Mahila participation does not create a second global NSS identity.

The common identity chain remains:

```text
┌──────────────┐
│    PERSON    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  MEMBERSHIP  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ SANGHA SEVI  │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ MAHILA PARTICIPATION │
└──────────────────────┘
```

The existing NSS ERP architecture states that Mahila uses the common NSS membership framework and does not create a separate NSS membership identity.

The Mahila Bye-Law nevertheless defines membership of the Mahila Sangha itself, including its qualifications and enrollment procedure.

Therefore the ERD distinguishes:

```text
NSS Membership Identity
        ≠
Mahila Sangha Participation / Affiliation
```

---

# 4. Person

`Person` is the authoritative identity entity.

Conceptually:

```text
PERSON
------
person_pk
```

The Mahila module does not duplicate:

* Name
* Gender
* Date of Birth
* Contact information
* Address
* Other core identity attributes

These remain owned by the Person module.

---

# 5. NSS Membership

NSS Membership remains the common membership identity framework.

Conceptually:

```text
PERSON
   │
   ▼
NSS MEMBERSHIP
   │
   ▼
SANGHA SEVI ID
```

The Mahila module references this identity.

It does not create a competing global membership ID.

---

# 6. Mahila Participation

The central Mahila-specific relationship is:

```text
MAHILA PARTICIPATION
```

Conceptually:

```text
PERSON / SANGHA SEVI
          │
          ▼
┌─────────────────────────┐
│ MAHILA PARTICIPATION    │
└────────────┬────────────┘
             │
             ├── Mahila Sangha
             ├── Status
             ├── Enrollment
             └── Cessation
```

The exact physical representation is deferred to the Table Design document.

---

# 7. Mahila Participation vs Membership

The ERD deliberately separates:

```text
NSS MEMBERSHIP
```

from:

```text
MAHILA PARTICIPATION
```

because the two have different authorities.

NSS Membership provides the common NSS identity.

Mahila participation represents the person's relationship with the Mahila Sangha.

This allows the system to preserve both:

```text
Global NSS identity
```

and:

```text
Mahila Sangha-specific participation
```

without creating duplicate Person records.

---

# 8. Mahila Sangha

The authoritative institution is:

```text
NILACHALA SARASWATA MAHILA SANGHA
```

The verified Bye-Law identifies it as a registered society with its registered office at Nilachala Kutir, Swargadwar, Puri.

Conceptually:

```text
KENDRA SANGHA
      │
      │ auspices / guidance
      ▼
MAHILA SANGHA
```

---

# 9. Organizational Relationship

The Mahila Sangha has an institutional relationship with Kendra Sangha.

The Bye-Law states that Mahila Sangha functions under the auspices of Nilachala Saraswata Sangha and that its functions and activities are performed according to established practices and conventions approved and directions issued by Kendra Sangha.

Conceptually:

```text
┌──────────────────────┐
│     KENDRA SANGHA    │
└──────────┬───────────┘
           │
           │ guidance / direction
           ▼
┌─────────────────────────────┐
│ NILACHALA SARASWATA         │
│ MAHILA SANGHA               │
└─────────────────────────────┘
```

---

# 10. General Body

The Bye-Law explicitly establishes the General Body.

It consists of:

```text
All Mahila Sangha Members
+
Members of the Governing Body
```

Governing Body members are therefore also members of the General Body.

Conceptually:

```text
MAHILA PARTICIPATION
        │
        ▼
GENERAL BODY MEMBERSHIP
```

---

# 11. Governing Body

The Mahila Bye-Law establishes a Governing Body of nine members.

Conceptually:

```text
                    ┌─────────────────────┐
                    │ MAHILA GOVERNING    │
                    │ BODY                │
                    │ 9 MEMBERS           │
                    └──────────┬──────────┘
                               │
       ┌────────┬────────┬─────┼──────┬────────┬──────────┐
       ▼        ▼        ▼     ▼      ▼        ▼          ▼
   President  Vice-   Parichalak Secretary Joint   Treasurer Other
              President                  Secretary Members
```

The Bye-Law explicitly lists:

1. President
2. Vice-President
3. Parichalak
4. Secretary
5. Joint Secretary
6. Treasurer
7. Three other members.

---

# 12. Unified Governance Model

The ERP uses the common Unified Body Governance Model.

Conceptually:

```text
COMMON GOVERNANCE
       │
       ▼
BODY MASTER
       │
       ▼
MAHILA GOVERNING BODY
       │
       ▼
BODY MEMBER ASSIGNMENT
       │
       ▼
POSITION
```

The Mahila module provides the Mahila-specific rules for the body.

It does not create a completely independent governance engine.

---

# 13. Governing Body Member Assignment

The conceptual relationship is:

```text
MAHILA GOVERNING BODY
          │
          │ 1 : N
          ▼
GOVERNANCE MEMBER ASSIGNMENT
          │
          ├── Person
          ├── Position
          ├── Term
          ├── Effective From
          └── Effective To
```

This supports historical office-bearer records.

---

# 14. Position Relationship

The Mahila Governing Body uses the following positions:

```text
PRESIDENT
VICE_PRESIDENT
PARICHALAK
SECRETARY
JOINT_SECRETARY
TREASURER
MEMBER
```

The `MEMBER` position can represent the three ordinary Governing Body members.

The exact physical position-master representation belongs to the common Governance module.

---

# 15. Nine-Member Governing Body Constraint

Conceptually:

```text
MAHILA GOVERNING BODY
        │
        └── exactly 9 positions/assignments
```

Required composition:

```text
1 President
1 Vice-President
1 Parichalak
1 Secretary
1 Joint Secretary
1 Treasurer
3 Members
```

The physical implementation shall enforce this through governance/business-rule validation rather than duplicating a Mahila-specific governance engine.

---

# 16. Founder President and Permanent Vice-President

The Bye-Law provides special treatment for the two original Sevikas:

```text
Founder President
Permanent Vice-President
```

while they prefer to continue serving in those capacities.

Conceptually:

```text
GOVERNING BODY ASSIGNMENT
        │
        ├── Position
        ├── Person
        ├── Effective From
        ├── Effective To
        └── Tenure Type
```

The governance model must support special/historical tenure characteristics.

---

# 17. Parichalak Relationship

The Parichalak is a member of the Mahila Governing Body and also has specific authority under the Bye-Law.

Conceptually:

```text
PERSON
   │
   ▼
GOVERNING BODY ASSIGNMENT
   │
   └── Position = PARICHALAK
```

The Parichalak's additional authority is represented through the Governance/RBAC layer rather than a duplicate person or role table.

---

# 18. Membership Enrollment Relationship

The Bye-Law states that the Parichalak enrolls members from among female devotees who meet the stated qualifications.

Conceptually:

```text
PERSON
   │
   ▼
Eligibility
   │
   ▼
PARICHALAK ENROLLMENT
   │
   ▼
MAHILA PARTICIPATION
```

The enrollment action should be auditable.

---

# 19. Membership Cessation Relationship

Membership may cease because of:

```text
DEATH
RESIGNATION
RULE VIOLATION
```

The Bye-Law states that death and resignation automatically cease membership, while the Parichalak may order cessation for violation following a Secretary's report.

Conceptually:

```text
MAHILA PARTICIPATION
       │
       ▼
CESSATION
       │
 ┌─────┼────────────┐
 ▼     ▼            ▼
Death Resignation Rule Violation
                       │
                       ▼
              Secretary Report
                       │
                       ▼
                  Parichalak
                       │
                       ▼
                   Cessation
```

---

# 20. Membership History

Mahila participation history must preserve:

```text
Enrollment
Status
Cessation
Cessation Reason
Authority
Effective Date
```

Conceptually:

```text
MAHILA PARTICIPATION
        │
        ▼
MAHILA PARTICIPATION HISTORY
```

Historical records must not be silently overwritten.

---

# 21. General Body Relationship

The General Body is not a second membership identity.

It is a governance participation context derived from Mahila Sangha membership.

Conceptually:

```text
MAHILA MEMBER
      │
      ▼
GENERAL BODY
      │
      ├── Meetings
      ├── Information
      └── Applicable resolutions
```

---

# 22. Activity Relationship

Mahila Sangha activities originate from its institutional objectives.

The Bye-Law identifies activities including:

* Regular meetings.
* Discourses.
* Training centres.
* Seminars.
* Educational institutions.
* Seva Puja.
* Other approved activities.

Conceptually:

```text
MAHILA SANGHA
      │
      ▼
ACTIVITY / EVENT
      │
      ├── Participants
      ├── Attendance
      ├── Schedule
      └── Location
```

---

# 23. Common Event Framework

The Mahila module should use the common Event framework for activities requiring event management.

Conceptually:

```text
MAHILA ACTIVITY
      │
      ▼
COMMON EVENT
      │
      ▼
EVENT PARTICIPATION
      │
      ▼
ATTENDANCE
```

The old draft `mahila_activity` / `mahila_activity_participant` proposal must therefore be evaluated against the common Event framework during Table Design.

No duplicate event architecture is frozen by this ERD.

---

# 24. Seva Puja Relationship

Seva Puja is explicitly part of Mahila Sangha activities.

The Bye-Law states that Seva Puja at Nilachala Kutir is performed according to established practices and conventions approved and directions issued by Kendra Sangha.

Conceptually:

```text
KENDRA SANGHA
      │
      ▼
MAHILA SANGHA
      │
      ▼
SEVA PUJA ACTIVITY
      │
      ├── Seva
      ├── Participants
      └── Attendance
```

Detailed Seva-Puja rules remain outside this ERD unless the common Seva-Puja module defines them as Mahila-specific.

---

# 25. Training Relationship

The Bye-Law permits training centres and practical/theoretical training intended to develop ideal Sevikas.

Conceptually:

```text
MAHILA SANGHA
      │
      ▼
TRAINING / EDUCATIONAL ACTIVITY
      │
      ├── Participants
      ├── Schedule
      └── Attendance
```

The physical Training model is not frozen by this ERD.

---

# 26. Nilachala Kutir Relationship

Nilachala Kutir is the registered office and a central activity location.

Conceptually:

```text
MAHILA SANGHA
      │
      ▼
NILACHALA KUTIR
      │
      ├── Meetings
      ├── Seva Puja
      ├── Training
      └── Educational Activities
```

The actual location master remains owned by the common Location/Organization framework.

---

# 27. Finance Relationship

The Mahila Sangha maintains funds and accounts under its Bye-Law.

Conceptually:

```text
MAHILA SANGHA
      │
      ▼
COMMON FINANCE
      │
      ├── Receipts
      ├── Donations
      ├── Grants
      ├── Expenditure
      └── Accounts
```

The Mahila module provides Mahila-specific finance rules.

---

# 28. Donation Relationship

The Bye-Law recognizes several sources of funds, including voluntary donations, specific-purpose donations, grants and other contributions.

Conceptually:

```text
DONOR / SOURCE
      │
      ▼
FINANCIAL RECEIPT
      │
      ├── General Fund
      └── Specific Purpose
```

Specific-purpose donations must remain traceable to their specified purpose because the Bye-Law requires them to be used for that purpose.

---

# 29. Audit Relationship

The Bye-Law requires annual audit by a qualified auditor.

The audit report flows:

```text
ACCOUNTS
   │
   ▼
QUALIFIED AUDITOR
   │
   ▼
AUDIT REPORT
   │
   ▼
GOVERNING BODY
   │
   ▼
GENERAL BODY
```

The ERP should preserve these approval relationships.

---

# 30. Amendment Relationship

The Bye-Law permits the Governing Body to amend provisions subject to the specified process, including prior consultation with the President of Nilachala Saraswata Sangha and subsequent placement before the General Body for information.

Conceptually:

```text
GOVERNING BODY
      │
      ▼
AMENDMENT PROPOSAL
      │
      ▼
KENDRA PRESIDENT CONSULTATION
      │
      ▼
GENERAL BODY INFORMATION
```

The actual document/version repository remains a common Documentation/Governance capability.

---

# 31. Dissolution Relationship

The Bye-Law specifies that on dissolution, remaining property after satisfying debts and liabilities vests in Kendra Sangha.

Conceptually:

```text
MAHILA SANGHA
      │
      ▼
DISSOLUTION
      │
      ▼
LIABILITIES SETTLED
      │
      ▼
REMAINING PROPERTY
      │
      ▼
KENDRA SANGHA
```

---

# 32. Mahila Parichalana Mandali — ERD Clarification

"Mahila Parichalana Mandali" is the Odia/organizational terminology for the same Mahila Governing Body defined by the verified Bye-Law.

```text
MAHILA GOVERNING BODY = MAHILA PARICHALANA MANDALI
```

The ERD treats them as **one entity**:

```text
MAHILA GOVERNING BODY
(Mahila Parichalana Mandali)
        │
        ▼
9 members, 2-year term
Joint Secretary
Unified Governance Model
```

This is the authoritative Bye-Law-mandated governance entity for the Mahila Sangha.

---

# 33. Source Classification

Every ERD relationship shall be classified conceptually as one of:

```text
BYE-LAW
NSS GOVERNANCE
ERP DESIGN
PENDING
```

Examples:

```text
9-member Mahila Governing Body
→ BYE-LAW

General Body
→ BYE-LAW

Mahila Parichalana Mandali
→ BYE-LAW (same as Mahila Governing Body)

Unified Governance Model
→ NSS GOVERNANCE

Event Participation
→ ERP DESIGN USING COMMON EVENT FRAMEWORK
```

---

# 34. Core Conceptual ERD

```text
                         ┌─────────────────┐
                         │     PERSON      │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   MEMBERSHIP    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  SANGHA SEVI    │
                         └────────┬────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  MAHILA PARTICIPATION    │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼───────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
      PARTICIPATION         GOVERNANCE         ACTIVITIES
        HISTORY                 │                   │
              │                 ▼                   ▼
              │       GOVERNING BODY         COMMON EVENT
              │                │                   │
              │                ▼                   ▼
              │        BODY MEMBER          PARTICIPATION
              │        ASSIGNMENT               │
              │                                 ▼
              │                           ATTENDANCE
              │
              ▼
       CESSATION HISTORY


        KENDRA SANGHA
              │
              │ guidance / auspices
              ▼
        MAHILA SANGHA
              │
       ┌──────┼─────────┐
       │      │         │
       ▼      ▼         ▼
   GOVERNANCE ACTIVITIES FINANCE
       │      │         │
       ▼      ▼         ▼
   GB / GB   EVENTS    ACCOUNTS
```

---

# 35. Governance ERD

```text
┌─────────────────────┐
│   MAHILA SANGHA     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ GOVERNING BODY      │
│ 9 MEMBERS           │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│ BODY MEMBER ASSIGNMENT   │
└────────────┬─────────────┘
             │
       ┌─────┴─────────────┐
       ▼                   ▼
    PERSON              POSITION
                           │
       ┌───────────────────┼──────────────────┐
       ▼                   ▼                  ▼
  PRESIDENT          PARICHALAK          SECRETARY
  VICE-PRESIDENT     JOINT SECRETARY     TREASURER
                     MEMBER × 3
```

---

# 36. Membership ERD

```text
PERSON
  │
  ▼
NSS MEMBERSHIP
  │
  ▼
SANGHA SEVI ID
  │
  ▼
MAHILA PARTICIPATION
  │
  ├── Enrollment
  ├── Current Status
  ├── History
  └── Cessation
```

This preserves the common NSS identity while representing Mahila-specific participation.

---

# 37. Activity ERD

```text
MAHILA SANGHA
      │
      ▼
COMMON EVENT
      │
      ├── Event Type
      ├── Date / Time
      ├── Location
      └── Host
            │
            ▼
    EVENT PARTICIPATION
            │
            ▼
       ATTENDANCE
```

Potential event/activity types include:

```text
REGULAR_MEETING
DISCOURSE
SEVA_PUJA
TRAINING
SEMINAR
EDUCATIONAL_ACTIVITY
OTHER_APPROVED_ACTIVITY
```

These are conceptual categories and are not yet frozen master data.

---

# 38. Finance ERD

```text
MAHILA SANGHA
      │
      ▼
FINANCE
      │
 ┌────┼───────────┐
 ▼    ▼           ▼
RECEIPT DONATION GRANT
 │
 ▼
FUND / PURPOSE
 │
 ▼
EXPENDITURE
```

Audit:

```text
ACCOUNTS
   │
   ▼
AUDIT
   │
   ▼
GOVERNING BODY APPROVAL
   │
   ▼
GENERAL BODY APPROVAL
```

---

# 39. Historical Governance ERD

The governance model must preserve historical assignments.

```text
PERSON
  │
  ▼
BODY MEMBER ASSIGNMENT
  │
  ├── Position
  ├── Start Date
  ├── End Date
  ├── Appointment/Selection Source
  └── Status
```

This allows the ERP to answer:

* Who was President during a particular period?
* Who was Parichalak?
* Who served as Secretary?
* Which members formed a particular Governing Body?
* When did a member leave office?

---

# 40. Governance and Person Separation

A person may have:

```text
Person
   │
   ├── Mahila Member
   │
   ├── General Body Member
   │
   └── Governing Body Assignment
```

The governance position is an assignment.

It is not a permanent attribute of the Person.

---

# 41. Governance and Membership Separation

Holding a Governing Body position does not create a separate membership identity.

```text
Mahila Member
      │
      ▼
Governance Assignment
```

not:

```text
Mahila Member
      │
      ▼
New Governance Member Identity
```

---

# 42. Event and Governance Separation

A person attending a Mahila event does not automatically become:

* Governing Body member
* General Body office-bearer
* Mahila administrator

Event participation and governance assignment remain independent relationships.

---

# 43. Finance and Governance Separation

Financial authorization is associated with the applicable governance position and financial workflow.

The system should not encode financial authority simply as:

```text
person.is_finance_admin = true
```

Instead:

```text
Person
   ↓
Governance Position
   ↓
RBAC / Financial Permission
   ↓
Financial Action
```

---

# 44. Audit Relationship

All important Mahila lifecycle and governance actions are auditable.

Conceptually:

```text
BUSINESS EVENT
      │
      ▼
AUDIT EVENT
```

Examples:

```text
Member Enrollment
Membership Cessation
Governing Body Assignment
Office Bearer Change
Finance Approval
Audit Approval
Amendment
Dissolution
```

Audit implementation belongs to the common Audit framework.

---

# 45. Organizational Scope

Mahila records must carry or derive the applicable organizational scope.

Potential scope:

```text
KENDRA
SAKHA
MAHILA SANGHA
```

The exact organization hierarchy is owned by the Organization module.

The Mahila ERD does not create a duplicate organizational master.

---

# 46. Sakha-Level Mahila Relationship

Existing NSS source material indicates that Mahila Sanghas may operate in association with Sakha Sanghas and are affiliated to Kendra Sangha.

Where this relationship is confirmed by the authoritative organizational documentation, it should be represented as:

```text
SAKHA
  │
  ▼
MAHILA SANGHA CONTEXT
```

without creating a second Sakha master.

The exact branch-level governance structure remains subject to the applicable authoritative rules.

---

# 47. Cross-Sangha Participation

Participation in a Mahila activity should not automatically change a person's organizational identity.

For example:

```text
Member's Mahila affiliation = Sakha A
                 │
                 ▼
Attends Mahila activity at Sakha B
                 │
                 ▼
Event Participation only
```

No transfer is implied by attendance.

---

# 48. Data Ownership Summary

| Entity / Concept           | Owner                              |
| -------------------------- | ---------------------------------- |
| Person                     | Person Module                      |
| NSS Membership             | Membership Module                  |
| Sangha Sevi ID             | Membership Module                  |
| Organization / Sakha       | Organization Module                |
| Mahila Participation       | Mahila Module                      |
| Mahila Governance Rules    | Mahila Module + Common Governance  |
| Governing Body             | Common Governance                  |
| Position                   | Common Governance                  |
| General Body               | Common Governance                  |
| Event                      | Common Event                       |
| Attendance                 | Common Attendance                  |
| Finance                    | Common Finance                     |
| Audit                      | Common Audit                       |
| RBAC                       | Administration                     |
| Kendra Relationship        | Organization / Governance          |
| Mahila Parichalana Mandali | Common Governance (= Mahila Governing Body) |

---

# 49. Cardinality Summary

| Relationship                              |                               Cardinality |
| ----------------------------------------- | ----------------------------------------: |
| Person → NSS Membership                   |                   Common Membership model |
| Membership → Sangha Sevi                  |                   Common Membership model |
| Person/Sangha Sevi → Mahila Participation | 1 : 0..N historical/participation context |
| Mahila Participation → History            |                                     1 : N |
| Mahila Sangha → General Body              |                     1 : 1 conceptual body |
| Mahila Sangha → Governing Body            |                        1 : 1 current body |
| Governing Body → Member Assignment        |                                     1 : N |
| Person → Governance Assignment            |                          1 : N historical |
| Mahila Sangha → Event                     |                                     1 : N |
| Event → Event Participation               |                                     1 : N |
| Event Participation → Attendance          |                    0..1 applicable record |
| Mahila Sangha → Finance Records           |                                     1 : N |
| Finance → Audit                           |                          1 : N / periodic |
| Kendra Sangha → Mahila Sangha             |                Institutional relationship |

---

# 50. Physical Schema Boundary

This ERD does not freeze:

* Table names
* Primary keys
* Foreign keys
* PostgreSQL types
* Indexes
* Constraints
* Triggers
* Materialized views
* Exact Finance implementation
* Exact Event implementation
* Exact branch-level Mahila organizational tables

Those decisions belong to:

```text
05_mahila_table_design.md
```

---

# 51. Deprecated/Unresolved Old Design Elements

The existing draft table design proposed:

```text
mahila_activity
mahila_activity_participant
```

These are not automatically retained.

They must be evaluated against the common Event framework.

Similarly, the ERD does not automatically introduce:

```text
mahila_member
mahila_governing_body
mahila_general_body
mahila_finance
mahila_audit
```

as independent physical tables.

The Unified Governance, Finance and Audit frameworks should be reused wherever applicable.

---

# 52. Terminology Clarification — Mahila Parichalana Mandali

"Mahila Parichalana Mandali" is the Odia/organizational term for the Mahila Governing Body defined by the verified Bye-Law.

They are one entity:

```text
Mahila Governing Body = Mahila Parichalana Mandali
```

The verified Bye-Law establishes:
* 9-member composition
* 2-year term
* Joint Secretary (not Assistant Secretary)
* Constitution process via Parichalak with President's consent

The ERD represents this as a single governance body through the Unified Governance Model.

---

# 53. ERD Design Rules

The conceptual model shall follow:

1. Person remains authoritative.
2. NSS Membership remains authoritative.
3. Sangha Sevi ID remains the global NSS membership identity.
4. Mahila participation does not create a duplicate NSS identity.
5. Mahila membership/participation history is preserved.
6. Governing Body is a governance body, not a membership table.
7. General Body is a governance context.
8. Office-bearer positions are assignments.
9. Governance assignments are historical.
10. Event participation is separate from governance.
11. Attendance is separate from event intention/participation.
12. Finance uses the common Finance framework.
13. Audit uses the common Audit framework.
14. RBAC uses centralized Administration.
15. Kendra relationship is preserved.
16. Cross-Sangha event attendance does not automatically transfer affiliation.
17. Bye-Law facts are not mixed with ERP assumptions.
18. Historical business records are preserved.
19. Physical table design is deferred to Step M-05.
20. No SQL is generated during this documentation phase.

---

# 54. ERD Freeze Status

### Supported by Verified Mahila Bye-Law

```text
✓ Mahila Sangha
✓ Membership qualification concept
✓ Parichalak enrollment
✓ Membership cessation
✓ General Body
✓ 9-member Governing Body
✓ President
✓ Vice-President
✓ Parichalak
✓ Secretary
✓ Joint Secretary
✓ Treasurer
✓ Three other members
✓ Governing Body term
✓ Founder President provision
✓ Permanent Vice-President provision
✓ Seva Puja
✓ Training / educational activities
✓ Finance
✓ Audit
✓ Amendment
✓ Dissolution
```

These are directly supported by the supplied Bye-Law.

### Supported by Existing NSS ERP Architecture

```text
✓ Common Person identity
✓ Common NSS Membership
✓ Sangha Sevi identity
✓ Unified Governance Model
✓ Common Event framework
✓ Common Attendance framework
✓ Common Finance framework
✓ Common Audit framework
✓ Centralized RBAC
```

### Pending / Requires Further Source Validation

```text
? Exact Sakha-level Mahila organizational structure
? Detailed Mahila event rules
? Detailed Mahila attendance rules
? Exact Mahila participation status model
? Exact physical representation of Mahila activities
```

---

# 55. Related Documents

```text
01_mahila_module_overview.md
02_mahila_erd.md
03_mahila_lifecycle.md
04_mahila_business_rules.md
05_mahila_table_design.md
```

Related common modules:

```text
Person
Membership
Organization
Governance
Event
Attendance
Finance
Audit
Administration / RBAC
```

---

# 56. Next Step

The next document is:

```text
03_mahila_lifecycle.md
```

It will define:

```text
Mahila Enrollment
       ↓
Active Participation
       ↓
Governance Eligibility
       ↓
Governing Body Assignment
       ↓
Term / Continuation
       ↓
Resignation / Death / Cessation
       ↓
Historical Record
```

and will distinguish **Mahila Sangha membership lifecycle** from **Governing Body office lifecycle**.

---

# End of Document
