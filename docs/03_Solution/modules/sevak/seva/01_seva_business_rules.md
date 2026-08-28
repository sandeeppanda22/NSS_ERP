# NSS ERP — Seva Business Rules

**Document ID:** SOL-SEV-SEVA-001  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** General Seva Assignment and Participation

---

# 1. Purpose

This document defines the common business rules governing **Seva participation and Seva assignments**.

Seva is a service activity and is separate from:

- NSS Membership
- Sevak participation status
- Sevak Sangha session attendance
- Anchalika/Zilla Sevak Sangha Puja attendance

---

# 2. Fundamental Distinction

The following are separate concepts:

```text
NSS Membership
        ≠
Sevak Participation
        ≠
Seva Assignment
        ≠
Event Attendance
```

In particular:

```text
ACTIVE Sevak
    ≠
Automatically assigned to Seva
```

and:

```text
Attendance at Sevak Sangha
    ≠
Seva Assignment
```

---

# 3. Seva Eligibility

Seva is not restricted by the male-only participation rule applicable to Sevak Sangha activities.

Eligible Seva participants may be:

```text
Male
Female
```

subject to the eligibility requirements of the specific Seva Category.

Therefore:

```text
Sevak Sangha Participation
    → Male participation rule

Seva Assignment
    → Male or Female
```

The gender rule for Sevak Sangha participation shall never be inherited automatically by the Seva system.

---

# 4. Seva Category

Every Seva assignment shall be associated with a Seva Category.

Seva Categories shall be maintained as master data.

They shall not be hard-coded into the Sevak table or application logic.

Conceptually:

```text
Seva Category Master
        ↓
Seva Assignment
        ↓
Person / Eligible Participant
```

A Seva Category may define its own eligibility criteria.

Such criteria may include, where applicable:

* Organizational level
* Required role
* Required qualification
* Required experience
* Gender, if genuinely required by that specific Seva
* Other approved category-specific conditions

The general Sevak Sangha gender rule shall not be used as a default Seva restriction.

---

# 5. Seva Assignment

A Seva Assignment represents an approved service responsibility associated with a person.

Conceptually:

```text
Person / Sevak
        ↓
Seva Assignment
        ↓
Seva Category
```

The assignment shall have its own lifecycle.

It shall not simply be represented as a single Seva Category field on the Sevak record.

---

# 6. Seva Assignment and Sevak Status

Sevak status and Seva Assignment status are independent.

```text
Sevak Status
    ACTIVE / INACTIVE
```

is separate from:

```text
Seva Assignment Status
```

Therefore:

```text
ACTIVE Sevak
    ↓
May have
    ↓
Approved Seva Assignment(s)
```

but:

```text
ACTIVE Sevak
    ≠
Automatically approved for every Seva
```

Similarly:

```text
INACTIVE Sevak
    ≠
All Seva Assignments automatically deleted
```

---

# 7. Multiple Seva Assignments

A Sevak may have multiple active Seva Assignments simultaneously.

Example:

```text
Sevak
 ├── Seva Assignment A → ACTIVE
 ├── Seva Assignment B → ACTIVE
 └── Seva Assignment C → ACTIVE
```

A Sevak may also simultaneously hold assignments across applicable Seva scopes, including:

```text
Sakha Seva
+
UPBS Seva
```

subject to the respective approval requirements.

---

# 8. Independent Assignment Lifecycle

Each Seva Assignment shall independently maintain:

* Seva Category
* Request/recommendation origin
* Approval workflow
* Approval authority
* Assignment status
* Effective date
* End/history information
* Audit trail

Approval of one assignment shall not automatically approve another.

Rejection or inactivation of one assignment shall not automatically change:

* Overall Sevak status
* Other Seva assignments
* Other Seva requests

---

# 9. Seva Assignment Origin

A Seva Assignment workflow may originate from either:

```text
SEVAK_REQUEST
```

or:

```text
SEVA_HEAD_RECOMMENDATION
```

The origin shall be recorded.

---

# 10. Sevak-Requested Seva

A Sevak may request a Seva Category.

The workflow is:

```text
Sevak
    ↓
Select / Request Seva Category
    ↓
Seva Head Review
    ↓
Approval / Rejection
```

For regular Sakha Seva, the approval continues:

```text
Seva Head
    ↓
Sakha President
    ↓
Approved Assignment
```

The request and approved assignment are separate concepts.

---

# 11. Seva Head Recommendation

A Seva Head may identify a suitable person for a Seva Category and recommend or assign the person for consideration.

The workflow is:

```text
Seva Head
    ↓
Recommend / Assign Seva Category
    ↓
Sevak Review / Acceptance
    ↓
Applicable Approval
    ↓
Approved Seva Assignment
```

The source of the workflow shall be recorded as:

```text
SEVA_HEAD_RECOMMENDATION
```

---

# 12. Request and Assignment Separation

A Seva request is not itself an approved Seva Assignment.

Conceptually:

```text
Seva Request / Recommendation
        ↓
Review
        ↓
Approval
        ↓
Seva Assignment
```

This separation is required so that:

* rejected requests remain historical;
* approval history is preserved;
* multiple requests can exist;
* assignments can have an independent lifecycle.

---

# 13. Rejected Seva Request

If a Seva request is rejected:

```text
Request
   ↓
REJECTED
```

the request shall remain in history.

It shall not be deleted.

The rejection of one category does not prevent the Sevak from requesting another category.

Example:

```text
Request #1
Seva Category A
    ↓
REJECTED

Request #2
Seva Category B
    ↓
APPROVED
```

Each request remains independently traceable.

---

# 14. New Seva Request After Rejection

A Sevak may request another Seva Category after rejection.

A rejected request shall not be overwritten by the new request.

The ERP shall preserve the complete request history.

---

# 15. Regular Sakha Seva Approval

For regular Sakha-level Seva, the approved workflow is:

```text
Sevak / Recommendation
        ↓
Seva Category
        ↓
Seva Head
        ↓
Sakha President
        ↓
Approved Seva Assignment
```

The Seva Head's review and the Sakha President's approval are separate approval stages.

---

# 16. Seva Head Approval

The Seva Head reviews the proposed Seva assignment.

The Seva Head may:

```text
Approve / Recommend Forward
```

or:

```text
Reject
```

The exact workflow state names shall be finalized with the common approval/workflow standards.

The approval action shall be audited.

---

# 17. Sakha President Approval

For regular Sakha Seva, final approval requires the Sakha President.

The assignment shall not become an approved Sakha Seva assignment before the required approval is completed.

Therefore:

```text
Seva Head Approval
    ↓
Sakha President Approval
    ↓
Approved Assignment
```

---

# 18. UPBS Seva

UPBS Seva follows a separate approval hierarchy.

The common model is:

```text
Sevak
    ↓
UPBS Seva Category
    ↓
UPBS Seva Head
    ↓
Kendra
    ↓
Parichalak / President
    ↓
Approved Assignment
```

Detailed UPBS-specific rules are maintained separately in:

```text
02_upbs_seva_rules.md
```

---

# 19. Multiple Active Assignments

There is no general rule restricting a Sevak to one active Seva assignment.

A Sevak may simultaneously have:

```text
Seva A → ACTIVE
Seva B → ACTIVE
Seva C → ACTIVE
```

provided each assignment has completed its applicable approval process.

---

# 20. Assignment Independence

Each assignment is independent.

Example:

```text
Seva A → ACTIVE
Seva B → ACTIVE
Seva C → REJECTED
```

Changing Seva C does not change Seva A or Seva B.

Similarly:

```text
Seva A → INACTIVE
```

does not automatically make:

```text
Seva B → INACTIVE
```

---

# 21. Seva Assignment Status

The exact universal status vocabulary shall be aligned with the common workflow standards.

At minimum, the model must support the distinction between:

```text
Proposed / Requested
Approved
Active
Rejected
Ended / Inactive
```

The final database status codes shall be frozen during the Seva table-design phase.

This document therefore defines the business concepts without prematurely hard-coding the final database enumeration.

---

# 22. Effective Date

An approved Seva Assignment shall maintain an effective date.

The effective date represents when the approved assignment becomes applicable.

It shall be independent of:

* Request date
* Approval date
* Sevak enrollment date

Historical dates must be preserved.

---

# 23. Assignment End / History

When a Seva Assignment ends, its historical record shall be preserved.

The system shall not delete the assignment.

Conceptually:

```text
Seva Assignment
    ↓
ACTIVE
    ↓
ENDED / INACTIVE
    ↓
Historical Record
```

The exact end-date and reason model shall be finalized with the Seva table design and common lifecycle standards.

---

# 24. Membership Transfer

NSS Membership Transfer changes the person's current Sakha.

There is no independent Sevak transfer workflow for Seva.

Conceptually:

```text
NSS Membership Transfer
        ↓
Current Sakha Changes
        ↓
Seva Context Re-evaluated
```

---

# 25. Old Sakha Seva After Transfer

Sakha-specific Seva assignments associated with the previous Sakha shall remain permanently preserved as historical records.

They shall not be deleted.

Example:

```text
Before Transfer:

Sakha A
 ├── Seva A → ACTIVE
 └── Seva B → ACTIVE

Membership Transfer
        ↓
Sakha B

Historical:
 Sakha A
 ├── Seva A
 └── Seva B
```

The old Sakha Seva history remains available for reporting and audit.

---

# 26. New Sakha Seva After Transfer

After Membership Transfer, the Sevak may apply for Seva in the new Sakha.

A new Sakha Seva Assignment must follow the normal approval workflow.

Example:

```text
Sakha B
    ↓
Seva Category
    ↓
Seva Head
    ↓
Sakha President
    ↓
New Approved Assignment
```

The old Sakha assignment is not automatically converted into the new Sakha assignment.

A new assignment/context is created.

---

# 27. No Automatic Seva Transfer

A Membership Transfer shall not automatically convert:

```text
Old Sakha Seva
```

into:

```text
New Sakha Seva
```

The Sevak must follow the applicable new-Sakha Seva process.

This preserves clear historical responsibility and approval.

---

# 28. UPBS Seva After Membership Transfer

UPBS Seva is treated separately from Sakha-specific Seva.

Membership Transfer shall not automatically terminate an existing UPBS Seva Assignment.

Continuation, modification or ending of UPBS Seva follows the applicable UPBS/Kendra rules.

Detailed rules are maintained in:

```text
02_upbs_seva_rules.md
```

---

# 29. Sevak Inactivation

When a Sevak becomes:

```text
INACTIVE
```

existing active Seva Assignments shall **not automatically be terminated**.

Instead:

```text
Sevak
ACTIVE → INACTIVE
        ↓
Active Seva Assignments
        ↓
REVIEW REQUIRED
```

Each assignment shall be reviewed independently.

---

# 30. Sakha Seva Review After Inactivation

For regular Sakha Seva, the applicable Seva authority shall review the assignment.

The review shall determine whether the assignment should:

```text
Continue
```

or:

```text
End / Become Inactive
```

The review applies independently to each active assignment.

---

# 31. UPBS Seva Review After Inactivation

For UPBS Seva, the assignment shall be reviewed according to the applicable UPBS/Kendra authority structure.

The assignment shall not be automatically terminated solely because the Sevak status changed to `INACTIVE`.

Detailed UPBS review rules are maintained separately.

---

# 32. Independence of Sevak Status and Seva

The following combination is valid:

```text
Sevak Status = INACTIVE

Seva Assignment A = ACTIVE
```

provided the applicable Seva authority has reviewed and continued the assignment.

Similarly:

```text
Sevak Status = ACTIVE

Seva Assignment A = INACTIVE
```

is valid.

The two statuses must not be automatically synchronized.

---

# 33. Seva and Sevak Sangha Attendance

Attendance at a Sevak Sangha activity does not automatically:

* Create a Seva Assignment.
* Approve a Seva request.
* Change a Seva Category.
* Reactivate a Seva Assignment.
* Create a Seva Head recommendation.

Likewise, holding a Seva Assignment does not automatically mean the person attended a Sevak Sangha activity.

---

# 34. Seva and Gender

The male-only rule for Sevak Sangha participation does not apply to Seva.

Therefore:

```text
Female NSS Member
    ↓
May undertake Seva
```

subject to the applicable Seva Category eligibility and approval process.

A Seva Category may have its own legitimate eligibility criteria.

Such criteria must be explicitly defined for that Seva Category.

---

# 35. Seva Scope

A Seva may operate at different organizational scopes.

The project source identifies possible Seva scopes including:

* Kendra
* Anchalika
* Zilla
* Sakha
* Pathachakra

The scope of an individual Seva Category shall be maintained as part of the Seva master/context.

The same Seva Category may exist in multiple organizational contexts where permitted.

---

# 36. Seva Roles

The Seva system may support roles such as:

* Seva Head
* Seva Co-Head
* Seva Member
* Seva Volunteer

Role applicability depends on the Seva context and organizational level.

These roles are distinct from the person's general Sevak status.

---

# 37. Seva Head

A Seva Head is responsible for the applicable Seva Category or Seva context.

The Seva Head may:

* Review Seva requests.
* Recommend/assign persons.
* Participate in approval.
* Review active assignments.
* Participate in assignment continuation/closure decisions.

Detailed RBAC permissions are governed centrally by the Administration/RBAC module.

---

# 38. Seva Category Master

The Seva Category Master shall contain the authoritative definition of each Seva.

At minimum, a Seva Category should support:

```text
Seva Code
Seva Name
Scope
Eligibility Criteria
Status
```

Additional attributes may be introduced as the Seva module is finalized.

Seva Category definitions shall be master-data driven.

---

# 39. Same Seva Across Multiple Organizations

The same Seva Category may exist in multiple organizational contexts.

Example:

```text
Seva Category A
    ├── Kendra
    ├── Anchalika
    ├── Zilla
    └── Sakha
```

The organizational context of an assignment must therefore be preserved.

---

# 40. Audit and History

The following shall be auditable:

* Seva request
* Seva recommendation
* Seva Category
* Seva Head review
* Approval
* Rejection
* Assignment creation
* Assignment activation
* Assignment continuation
* Assignment ending
* Membership Transfer impact
* Inactivation review
* Assignment status changes

Historical records shall not be physically deleted.

---

# 41. No Physical Deletion

Rejected requests, historical assignments and completed approval workflows shall remain available for audit and history.

The system shall not physically delete historical Seva records merely because:

* The request was rejected.
* The assignment ended.
* The Member transferred Sakha.
* The Sevak became INACTIVE.
* The Seva Category is no longer active.

---

# 42. Core Seva Workflow

### Sevak-requested Seva

```text
Eligible Person / Sevak
        ↓
Request Seva Category
        ↓
Seva Head Review
        ↓
Sakha President / Applicable Authority
        ↓
Approved
        ↓
Seva Assignment
```

### Seva Head recommendation

```text
Seva Head
        ↓
Recommend Seva Category
        ↓
Sevak Review / Acceptance
        ↓
Applicable Approval
        ↓
Approved
        ↓
Seva Assignment
```

---

# 43. Membership Transfer Workflow

```text
NSS Membership Transfer
        ↓
Old Sakha Seva History Preserved
        ↓
New Sakha
        ↓
Sevak May Apply for New Seva
        ↓
Normal Seva Approval
        ↓
New Seva Assignment
```

Existing UPBS Seva is handled separately.

---

# 44. Sevak Inactivation Workflow

```text
Sevak ACTIVE
        ↓
INACTIVE
        ↓
Identify Active Seva Assignments
        ↓
Assignment Review
        ├── Continue
        └── End / Inactive
```

No automatic blanket termination is performed.

---

# 45. Relationship With UPBS

UPBS Seva is a specialized Seva context.

This document defines the common Seva principles.

UPBS-specific rules are maintained in:

```text
02_upbs_seva_rules.md
```

The UPBS document shall define its detailed:

* Eligibility
* Approval
* Kendra interaction
* Parichalak/President approval
* Assignment lifecycle
* Transfer handling
* Inactivation review

---

# 46. Relationship With Sevak Sangha Events

The following are separate:

```text
Sakha-Level Sevak Sangha Session
        ≠
Anchalika/Zilla Sevak Sangha Puja
        ≠
Seva Assignment
```

Attendance at either Sevak Sangha event does not itself constitute Seva.

---

# 47. Frozen Principles

The following principles are approved for General Seva:

* Seva is separate from Sevak status.
* Seva is separate from Sevak Sangha attendance.
* Seva Categories are master-data driven.
* Seva Categories are not hard-coded into the Sevak table.
* Seva eligibility may be defined independently for each category.
* Seva is not gender-restricted by the Sevak Sangha participation rule.
* Male and Female persons may undertake Seva subject to applicable category eligibility.
* A Sevak may have multiple active Seva Assignments simultaneously.
* Each Seva Assignment has its own lifecycle.
* Each assignment has its own approval history.
* One assignment does not automatically approve another.
* One assignment's rejection or inactivation does not change another assignment.
* Seva may originate from a Sevak request.
* Seva may originate from a Seva Head recommendation.
* Request and approved Assignment are separate concepts.
* Rejected requests remain in history.
* A Sevak may request another Seva Category after rejection.
* Regular Sakha Seva requires Seva Head and Sakha President approval.
* UPBS Seva follows a separate Kendra-level approval process.
* Membership Transfer changes the current Sakha.
* There is no independent Sevak Seva transfer workflow.
* Old Sakha Seva history remains permanently preserved.
* New Sakha Seva requires a new applicable request/recommendation and approval.
* UPBS Seva is not automatically terminated merely because of Membership Transfer.
* Sevak INACTIVE status does not automatically terminate Seva Assignments.
* Inactivation triggers independent review of active Seva Assignments.
* Each Seva Assignment may independently continue or end.
* Historical Seva records are never physically deleted.
* All Seva request, approval, assignment and status changes are auditable.

---

# 48. Related Documents

```text
../01_sevak_module_overview.md
../03_sevak_lifecycle.md
../04_sevak_participation_rules.md
../05_sevak_business_rules.md
../06_sevak_table_design.md

../sangha/01_sakha_sevak_sangha_session_rules.md
../sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md

02_upbs_seva_rules.md

../events/01_other_sevak_event_rules.md

../../administration/
../../attendance/
../../membership/
../../reports/
```

---

# End of Document
