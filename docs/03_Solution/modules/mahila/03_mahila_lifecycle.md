# NSS ERP — Mahila Sangha Lifecycle

**Document ID:** SOL-MAH-003  
**Version:** 2.1.0  
**Status:** DRAFT — BYE-LAW ALIGNED  
**Module:** Mahila Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle of:

1. Mahila Sangha membership/participation.
2. Mahila Sangha Governing Body constitution.
3. Governing Body office-bearer assignments.
4. Governing Body vacancies.
5. Historical governance records.
6. Mahila institutional activities where lifecycle tracking is required.

The lifecycle rules in this document are derived primarily from the approved Mahila Sangha Bye-Law.

---

# 2. Lifecycle Principles

The Mahila lifecycle shall follow these principles:

- No duplicate Person identity.
- Mahila participation remains associated with the authoritative NSS Person/Membership identity.
- Membership history is preserved.
- Governance assignments are historical.
- A Governing Body term is not silently overwritten by a later body.
- Cessation reasons are preserved.
- Vacancy appointments are recorded separately from the original appointment.
- Bye-Law-defined authorities are preserved.
- ERP workflow shall support the Bye-Law rather than redefine it.

---

# 3. Mahila Membership Lifecycle

The approved Bye-Law establishes:

```text
Eligibility
    ↓
Enrollment
    ↓
Mahila Sangha Membership
    ↓
Continued Membership
    ├── Death
    ├── Resignation
    └── Rule Violation
              ↓
       Cessation
```

The Bye-Law defines the qualifications for enrollment and gives the Parichalak authority to enroll qualifying female devotees.

---

# 4. Eligibility

The Bye-Law specifies minimum qualifications for enrollment.

The applicant:

* must possess good moral character;
* must have unshakable faith in the eternal existence of Sri Sri Thakur;
* must accept Him as the sole and supreme Guru and Ishta;
* should desire to regulate her life for Guru Seva;
* must have been duly enrolled as a member of a Mahila Sangha affiliated to Nilachala Saraswata Sangha.

These are source-derived membership qualifications.

The ERP shall not replace them with arbitrary technical eligibility rules.

---

# 5. Enrollment

The Bye-Law states:

```text
Parichalak
    ↓
enrols members
    ↓
from qualifying female devotees
```

The enrollment action shall be recorded with:

* Person/Membership identity.
* Enrollment date.
* Mahila Sangha context.
* Authority.
* Resulting status.
* Audit information.

The Parichalak is the authority specified by the Bye-Law for enrollment.

---

# 6. Enrollment vs NSS Membership

The common NSS ERP identity architecture remains authoritative.

Conceptually:

```text
Person
   ↓
NSS Membership
   ↓
Mahila Sangha Participation
```

The Mahila module does not create a duplicate global Sangha Sevi identity.

The Mahila Bye-Law's membership provisions are represented as Mahila-specific participation/affiliation rules over the common NSS identity framework.

---

# 7. Active Mahila Membership

After valid enrollment:

```text
MAHILA MEMBERSHIP
        ↓
ACTIVE
```

An active member may participate in applicable:

* General Body activities.
* Mahila Sangha activities.
* Meetings.
* Seva Puja-related activities.
* Training.
* Educational activities.
* Other approved activities.

Actual participation rights remain subject to applicable rules.

---

# 8. Membership Continuation

No periodic Mahila-specific renewal lifecycle is defined in the supplied Mahila Bye-Law.

Therefore this document shall not invent a separate Mahila renewal cycle.

Where the common NSS Membership framework applies, the common membership lifecycle remains authoritative.

Mahila-specific cessation remains governed by the Mahila Bye-Law.

---

# 9. Membership Cessation

The Bye-Law specifies three relevant cessation paths:

```text
1. Death
2. Resignation
3. Rule violation
```

Death and resignation automatically cease membership.

For rule violations, the Secretary reports the matter and the Parichalak may order cessation.

---

# 10. Cessation — Death

Lifecycle:

```text
ACTIVE
   ↓
DEATH RECORDED
   ↓
MAHILA MEMBERSHIP CEASED
```

The cessation should preserve:

* Effective date.
* Source of death information.
* Audit record.
* Previous Mahila status.

No historical record should be deleted.

---

# 11. Cessation — Resignation

Lifecycle:

```text
ACTIVE
   ↓
RESIGNATION
   ↓
MAHILA MEMBERSHIP CEASED
```

The Bye-Law states that membership automatically ceases after resignation.

The ERP should preserve the resignation record and effective date.

---

# 12. Cessation — Rule Violation

Lifecycle:

```text
ACTIVE
   ↓
RULE VIOLATION REPORTED
   ↓
SECRETARY REPORT
   ↓
PARICHALAK CONSIDERATION
   ↓
CESSATION ORDER
   ↓
MAHILA MEMBERSHIP CEASED
```

The Bye-Law specifically identifies the Secretary's report and Parichalak's authority in this process.

The ERP must not represent the report itself as cessation.

The cessation occurs only when the competent authority orders it.

---

# 13. Membership Lifecycle States

For ERP purposes, the conceptual states are:

```text
ELIGIBILITY_REVIEW
       ↓
ENROLLED
       ↓
ACTIVE
       │
       ├──────────────┐
       │              │
       ▼              ▼
RESIGNED           DECEASED
       │              │
       └──────┬───────┘
              ▼
           CEASED
```

For rule violation:

```text
ACTIVE
   ↓
RULE_VIOLATION_REPORTED
   ↓
PARICHALAK_ORDER
   ↓
CEASED
```

The exact master-data codes will be finalized in Business Rules/Table Design.

---

# 14. Historical Membership

The system must retain:

```text
Enrollment
Status changes
Resignation
Death
Rule-violation cessation
Authority
Effective dates
```

A member's historical Mahila relationship must remain queryable after cessation.

---

# 15. General Body Lifecycle

The General Body consists of all members of the Mahila Sangha, including Governing Body members.

Conceptually:

```text
ACTIVE MAHILA MEMBERS
        ↓
GENERAL BODY MEMBERSHIP
```

When Mahila membership ceases, the person's General Body membership associated with that Mahila membership also ceases.

Historical General Body participation remains preserved.

---

# 16. Governing Body Lifecycle

The Mahila Sangha's overall management is entrusted to a **9-member Governing Body**.

Conceptually:

```text
Governing Body Formation
        ↓
Constituted
        ↓
Assumes Office
        ↓
Two-Year Term
        ↓
Successor Constitution
        ↓
New Governing Body Assumes Office
```

---

# 17. Governing Body Composition

The Governing Body consists of:

```text
1 President
1 Vice-President
1 Parichalak
1 Secretary
1 Joint Secretary
1 Treasurer
3 Other Members
```

The Bye-Law explicitly defines this nine-member structure.

---

# 18. Initial / Special Office Holders

The Bye-Law identifies two original Sevikas with special positions:

```text
Founder President
Permanent Vice-President
```

They continue in those capacities while they prefer to serve in them.

The lifecycle model must therefore support a special/historical tenure type rather than forcing these assignments into an ordinary fixed-term model.

---

# 19. Parichalak Lifecycle

The Bye-Law specifies that the Parichalak of Nilachala Saraswata Sangha functions as the Parichalak of this Sangha and is a life member under the stated provision.

Therefore:

```text
PARICHALAK
    ↓
LIFE MEMBERSHIP / SPECIAL GOVERNANCE STATUS
```

This is a specific Bye-Law provision and should not be generalized to all Mahila office-bearers.

---

# 20. Initial Governing Body Formation

The Bye-Law provides that:

* The Governing Body consists of nine members.
* The two original Sevikas occupy the Founder President and Permanent Vice-President positions while they prefer to serve.
* The Parichalak functions as Parichalak.
* The remaining six members are nominated by the Parichalak with knowledge of the President.

Conceptually:

```text
Special Founding Positions
          +
Parichalak
          +
Six Nominated Members
          ↓
9-Member Governing Body
```

---

# 21. Governing Body Assumption of Office

The Governing Body's term is measured from the date it assumes office.

The Bye-Law specifies a two-year term from the date of assumption of office.

Therefore the ERP should record:

```text
Body Constitution Date
Term Start Date
Scheduled Term End Date
Actual Handover Date
```

---

# 22. Two-Year Term

The normal Governing Body term is:

```text
2 YEARS
```

This is a Mahila-specific Bye-Law rule.

It must not be replaced by the generic NSS three-year governance term.

The body continues after the prescribed two-year period until a new Governing Body is constituted and takes over charge.

---

# 23. Continuation After Term Expiry

Lifecycle:

```text
TERM ACTIVE
     ↓
TWO-YEAR TERM EXPIRES
     ↓
SUCCESSOR NOT YET CONSTITUTED?
     │
     └── YES
          ↓
CURRENT BODY CONTINUES
          ↓
UNTIL SUCCESSOR
CONSTITUTED AND
TAKES OVER
```

This is explicitly provided by the Bye-Law.

Therefore the ERP must distinguish:

```text
Scheduled Term End
```

from:

```text
Actual End of Office
```

---

# 24. Successor Governing Body Formation

After expiry of the term:

```text
Parichalak
     ↓
takes consensus of General Body
     ↓
announces list of members
     ↓
President's consent
     ↓
office-bearers announced
     ↓
new Governing Body constituted
```

The Bye-Law specifies this process.

---

# 25. Office-Bearer Selection Within New Body

The office-bearers identified in the Bye-Law are announced from among the members of the Governing Body.

The Parichalak does this in consultation with the President.

Therefore:

```text
Governing Body Members
        ↓
Office-Bearer Assignment
```

is a separate lifecycle step from constitution of the body.

---

# 26. President / Vice-President Vacancy

The Bye-Law specifically provides for the resignation or non-existence of the present President or Vice-President.

In such a case:

```text
Vacancy
   ↓
Governing Body consultation with Parichalak
   ↓
General Body meeting
   ↓
Election of President / Vice-President
```

The Secretary convenes the General Body meeting for this purpose.

---

# 27. Other Governing Body Vacancy

For a vacancy caused by non-existence or resignation of another Governing Body member:

```text
Vacancy
   ↓
Parichalak
   ↓
selects from among Sangha members
   ↓
fills vacancy
   ↓
unexpired portion of existing term
```

This is explicitly stated in the Bye-Law.

---

# 28. Vacancy Does Not Restart the Term

A replacement Governing Body member serves only:

```text
REMAINING / UNEXPIRED PORTION
```

of the existing term.

The vacancy appointment therefore does not create a new two-year term.

---

# 29. Office-Bearer Assignment Lifecycle

Conceptually:

```text
PERSON
   ↓
ELIGIBLE MEMBER
   ↓
GOVERNING BODY MEMBER
   ↓
POSITION ASSIGNED
   ↓
OFFICE HELD
   │
   ├── Normal term completion
   ├── Resignation
   ├── Non-existence
   └── Vacancy replacement
```

The governance assignment history remains permanently auditable.

---

# 30. Governing Body Historical Record

Every Governing Body should remain identifiable as a historical body.

Conceptually:

```text
GB-001
2024–2026

GB-002
2026–2028

GB-003
2028–2030
```

The actual dates depend on constitution and handover events.

The system must not overwrite GB-001 when GB-002 is created.

---

# 31. Governing Body Status

Conceptual lifecycle:

```text
FORMING
   ↓
CONSTITUTED
   ↓
ACTIVE
   ↓
TERM_EXPIRED_PENDING_SUCCESSOR
   ↓
CLOSED
```

`TERM_EXPIRED_PENDING_SUCCESSOR` is important because the Bye-Law explicitly permits the outgoing Governing Body to continue until the successor takes over.

---

# 32. Governing Body Member Status

A member assignment may conceptually be:

```text
NOMINATED
   ↓
ASSIGNED
   ↓
ACTIVE
   ↓
ENDED
```

or:

```text
ACTIVE
   ↓
RESIGNED
```

or:

```text
ACTIVE
   ↓
NON_EXISTENT / VACATED
```

The precise master values will be established in Business Rules.

---

# 33. Governance and Mahila Membership Dependency

A Governing Body member must be a member of the Mahila Sangha because the Bye-Law specifies that the Governing Body is composed from among Sangha members.

Therefore:

```text
Mahila Membership
      ↓
Governance Eligibility
      ↓
Governing Body Assignment
```

A person whose Mahila membership has ceased should not remain an active Governing Body member without an applicable authoritative rule.

The exact system handling of such a case will be defined in Business Rules.

---

# 34. Founder President / Permanent Vice-President Dependency

The Founder President and Permanent Vice-President provisions are special.

Their continuation is based on their preference to continue serving in those capacities.

Therefore the ERP must not automatically terminate these assignments merely because a normal Governing Body two-year term expires.

---

# 35. Parichalak and Governing Body Term

The Parichalak has a special status under the Bye-Law.

The normal two-year Governing Body term should therefore not be interpreted as terminating the Parichalak's special life-member status.

These are separate concepts:

```text
Governing Body Term
        ≠
Parichalak Life Membership
```

---

# 36. Activity Lifecycle

The Bye-Law identifies several classes of Mahila activities:

* Regular meetings.
* Discourses.
* Training centres.
* Seminars.
* Educational institutions.
* Seva Puja.
* Other approved activities.

The operational lifecycle is:

```text
PLANNED
   ↓
APPROVED
   ↓
SCHEDULED
   ↓
CONDUCTED
   ↓
CLOSED
```

This is an ERP implementation lifecycle, not a statutory status defined by the Bye-Law.

---

# 37. Event Participation Lifecycle

Where a Mahila activity uses the common Event framework:

```text
EVENT
   ↓
VISIBLE / PUBLISHED
   ↓
MEMBER INTEREST / REGISTRATION
   ↓
ATTENDANCE
   ↓
EVENT CLOSED
```

Detailed event rules are outside this document and will be defined by the common Event/Participation framework.

---

# 38. Seva Puja Lifecycle

The Bye-Law specifically identifies Seva Puja at Nilachala Kutir as a Mahila Sangha activity and places it within the practices/conventions approved and directed by Kendra Sangha.

The conceptual ERP lifecycle is:

```text
SEVA PUJA PLAN
      ↓
AUTHORIZATION / ARRANGEMENT
      ↓
SEVAK / SEVIKA ASSIGNMENT
      ↓
SEVA PUJA
      ↓
ACTIVITY RECORD
```

The Bye-Law specifically gives the Parichalak responsibility to appoint Sevaks and Sevikas for day-to-day Seva Puja.

---

# 39. Training / Educational Activity Lifecycle

Conceptually:

```text
PROPOSAL
   ↓
APPROVAL
   ↓
SCHEDULE
   ↓
TRAINING / EDUCATION
   ↓
COMPLETION
   ↓
HISTORICAL RECORD
```

The Bye-Law authorizes training centres, seminars and educational institutions attached to Nilachala Kutir.

Detailed operational rules are not defined by this lifecycle document.

---

# 40. Finance Lifecycle

The Mahila financial lifecycle is:

```text
RECEIPT / GRANT / DONATION
          ↓
FUND ACCOUNTING
          ↓
APPROVED EXPENDITURE
          ↓
ACCOUNTING
          ↓
ANNUAL AUDIT
          ↓
GOVERNING BODY APPROVAL
          ↓
GENERAL BODY APPROVAL
```

The Bye-Law requires annual audit and specifies the approval sequence.

---

# 41. Specific-Purpose Donation Lifecycle

For a specific-purpose donation:

```text
DONATION RECEIVED
      ↓
PURPOSE RECORDED
      ↓
FUND RETAINED FOR PURPOSE
      ↓
EXPENDITURE FOR SPECIFIED PURPOSE
      ↓
TRACEABLE RECORD
```

The Bye-Law explicitly requires such donations to be spent and utilized only for that purpose.

---

# 42. Audit Lifecycle

The annual audit lifecycle is:

```text
FINANCIAL YEAR
      ↓
ACCOUNTS PREPARED
      ↓
QUALIFIED AUDITOR
      ↓
AUDIT REPORT
      ↓
GOVERNING BODY
      ↓
FINAL APPROVAL
      ↓
GENERAL BODY
      ↓
APPROVAL
```

This sequence is explicitly stated in the Bye-Law.

---

# 43. Amendment Lifecycle

The Bye-Law permits amendment where necessary to give effect to its provisions or aims.

Conceptually:

```text
DIFFICULTY / NECESSITY IDENTIFIED
          ↓
GOVERNING BODY RESOLUTION
          ↓
PRIOR CONSULTATION WITH
KENDRA PRESIDENT
          ↓
ACTION UNDER RESOLUTION
          ↓
NEXT GENERAL BODY
          ↓
INFORMATION
```

Prior consultation with the President of Nilachala Saraswata Sangha is a stated pre-condition.

---

# 44. Dissolution Lifecycle

The Bye-Law provides for dissolution where the Sangha is not functioning toward its stated aims and objects.

Conceptually:

```text
DISSOLUTION CONDITION
       ↓
SANGHA DISSOLVED
       ↓
DEBTS / LIABILITIES SATISFIED
       ↓
REMAINING PROPERTY
       ↓
VESTS IN KENDRA SANGHA
```

The Kendra Sangha undertakes to fulfil the stated aims and objects.

---

# 45. Historical Preservation

The following must remain historically accessible:

```text
Membership
Enrollment
Cessation
Governing Bodies
Office Bearers
Vacancies
Activities
Seva Puja
Training
Finance
Audit
Amendments
Dissolution
```

No completed historical lifecycle record should be physically deleted merely because it is no longer current.

---

# 46. Lifecycle and Audit

Each significant transition should generate an audit record.

Examples:

```text
Mahila Enrollment
Membership Cessation
Governing Body Constitution
Office-Bearer Assignment
President Vacancy
Vice-President Vacancy
Other Member Vacancy
Governing Body Closure
Activity Approval
Finance Approval
Audit Approval
Bye-Law Amendment
```

The actual Audit implementation belongs to the common Audit module.

---

# 47. Lifecycle and Authorization

The lifecycle must respect the authorities defined by the Bye-Law.

Examples:

```text
Enrollment
→ Parichalak

Rule-Violation Cessation
→ Secretary Report → Parichalak Order

Governing Body Formation
→ Bye-Law-defined Parichalak / President / General Body process

President / Vice-President Vacancy
→ Governing Body + Parichalak + General Body process

Other Governing Body Vacancy
→ Parichalak

Seva Puja Sevak/Sevika Appointment
→ Parichalak
```

The system shall not substitute a generic administrator role for a Bye-Law-defined authority.

---

# 48. Lifecycle and Common NSS Governance

Where the Mahila Bye-Law defines a specific lifecycle, the Mahila rule takes precedence over generic governance defaults.

For example:

```text
Generic NSS Governance Term
        ≠
Mahila Governing Body Term
```

The Mahila Governing Body term is specifically **two years**, with continuation until the successor assumes charge.

---

# 49. Lifecycle and Common Membership

Mahila participation is attached to the common NSS Person/Membership identity.

Therefore:

```text
Person Lifecycle
        ↓
NSS Membership Lifecycle
        ↓
Mahila Participation Lifecycle
```

The Mahila lifecycle does not create an independent global member identity.

---

# 50. Lifecycle State History

Every lifecycle transition should conceptually record:

```text
Entity
Previous State
New State
Effective Date
Authority
Reason
Reference
Created By
Created At
```

This is an ERP auditability requirement, not a direct Bye-Law clause.

---

# 51. Important Source Boundary

The approved Mahila Bye-Law does not define all possible ERP lifecycle states.

Therefore states such as:

```text
ELIGIBILITY_REVIEW
ACTIVE
PENDING
APPROVED
SCHEDULED
CLOSED
```

are ERP lifecycle representations.

They must not be described as statutory terms unless the authoritative source uses them.

---

# 52. Mahila Parichalana Mandali

"Mahila Parichalana Mandali" is the Odia/organizational term for the same Mahila Governing Body defined by the verified Bye-Law.

```text
Mahila Governing Body = Mahila Parichalana Mandali
```

The lifecycle of this body is fully defined in Sections 16–31 of this document (Governing Body lifecycle).

There is no separate lifecycle to define — the Governing Body lifecycle IS the Mahila Parichalana Mandali lifecycle.

---

# 53. Lifecycle Summary

## Membership

```text
Eligibility
   ↓
Enrollment
   ↓
Active
   ├── Death → Ceased
   ├── Resignation → Ceased
   └── Rule Violation
           ↓
      Secretary Report
           ↓
       Parichalak Order
           ↓
          Ceased
```

## Governing Body

```text
Formation
   ↓
Constituted
   ↓
Assumes Office
   ↓
Two-Year Term
   ↓
Successor Formation
   ↓
Handover
   ↓
Historical / Closed
```

## Vacancy

```text
Vacancy
   ↓
Authority-specific process
   ↓
Replacement
   ↓
Unexpired Term
```

## Activities

```text
Plan
 ↓
Approve
 ↓
Schedule
 ↓
Conduct
 ↓
Close
```

## Finance

```text
Receive
 ↓
Account
 ↓
Authorize
 ↓
Spend
 ↓
Audit
 ↓
GB Approval
 ↓
General Body Approval
```

---

# 54. Lifecycle Rules Not Yet Frozen

The following require separate business-rule decisions or authoritative sources:

* Exact ERP Mahila participation status codes.
* Detailed Mahila event approval workflow.
* Detailed Mahila attendance rules.
* Detailed branch-level Mahila lifecycle.
* Detailed governance permission mapping.
* Digital representation of General Body resolutions.
* Detailed training completion lifecycle.
* Detailed financial approval workflow.

These should not be invented in this document.

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
Administration
```

---

# 56. Next Step

The next document is:

```text
04_mahila_business_rules.md
```

This document will consolidate the existing `MAH-*` rules with the verified Bye-Law-derived rules and clearly classify each rule as:

BYE-LAW
NSS GOVERNANCE
ERP DESIGN
PENDING

---

# End of Document
