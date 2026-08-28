# NSS ERP — UPBS Seva Rules

**Document ID:** SOL-SEV-SEVA-002  
**Version:** 1.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** UPBS Seva

---

# 1. Purpose

This document defines the business rules governing **UPBS Seva**.

UPBS Seva is a specialized Seva context and follows an approval process that is different from regular Sakha-level Seva.

The general Seva principles are defined in:

```text
01_seva_business_rules.md
```

This document defines only the UPBS-specific rules.

---

# 2. UPBS Seva Is Seva

UPBS Seva is part of the overall Seva framework.

Therefore:

```text
UPBS Seva
    ⊂
Seva
```

However, UPBS Seva has its own:

* Organizational context
* Seva categories
* Seva Head
* Kendra review
* Final approval authority
* Assignment lifecycle

---

# 3. UPBS Seva Is Separate From Sevak Sangha Participation

UPBS Seva and Sevak Sangha participation are independent concepts.

```text
Sevak Sangha Participation
        ≠
UPBS Seva Assignment
```

Participation in:

* Sakha-Level Sevak Sangha Session, or
* Anchalika/Zilla Sevak Sangha Puja

does not automatically create a UPBS Seva Assignment.

Likewise, a UPBS Seva Assignment does not automatically mean that the person attended a Sevak Sangha activity.

---

# 4. Gender Eligibility

UPBS Seva is not subject to the male-only participation rule of Sevak Sangha activities.

Eligible UPBS Seva participants may be:

```text
Male
Female
```

subject to the eligibility criteria of the applicable UPBS Seva Category.

Therefore:

```text
Sevak Sangha Event
    ↓
Male participation rule

UPBS Seva
    ↓
Male or Female
```

The gender rule shall be determined by the UPBS Seva Category where a category-specific restriction is genuinely required.

---

# 5. UPBS Seva Category

Every UPBS Seva Assignment shall be associated with a defined UPBS Seva Category.

UPBS Seva Categories shall be maintained as master data.

The category definition may include:

* UPBS Seva Code
* UPBS Seva Name
* Eligibility criteria
* Organizational scope
* Status
* Other category-specific attributes

UPBS Seva Categories shall not be hard-coded into the Sevak record.

---

# 6. UPBS Seva Eligibility

Eligibility shall be determined from authoritative ERP data.

The system may consider:

* Person
* NSS Membership
* Current organizational association
* Sevak participation where applicable
* UPBS Seva Category eligibility
* Existing UPBS assignments
* Required qualifications or other category-specific conditions

Eligibility does not itself constitute an assignment.

Therefore:

```text
Eligible
   ≠
Approved
   ≠
Assigned
```

---

# 7. UPBS Seva Request

A person/Sevak may apply for an eligible UPBS Seva Category.

The request shall be recorded independently from the eventual assignment.

Conceptually:

```text
Eligible Person / Sevak
        ↓
UPBS Seva Request
        ↓
UPBS Seva Head Review
        ↓
Kendra Submission
        ↓
Approval
        ↓
UPBS Seva Assignment
```

---

# 8. UPBS Seva Head

The UPBS Seva Head is responsible for the initial review of UPBS Seva requests/recommendations.

The UPBS Seva Head may:

* Review eligibility
* Review the requested Seva
* Recommend the person
* Forward the request to Kendra
* Reject the request where applicable

The review action shall be recorded and auditable.

---

# 9. UPBS Seva Head Recommendation

A UPBS Seva Head may recommend a person for a UPBS Seva Category.

The workflow shall preserve the distinction between:

```text
REQUEST
```

and:

```text
RECOMMENDATION
```

The source of the workflow shall be recorded.

Possible origins include:

```text
SEVAK_REQUEST
UPBS_SEVA_HEAD_RECOMMENDATION
```

---

# 10. Kendra Submission

After UPBS Seva Head review/recommendation, the applicable request is submitted to Kendra for approval.

The workflow is:

```text
UPBS Seva Head
        ↓
Kendra
        ↓
Approval Authority
```

A UPBS Seva Head shall not independently finalize a UPBS Seva Assignment where Kendra approval is required.

---

# 11. Final Approval Authority

The final approval for UPBS Seva is at Kendra level.

The approval authority is:

```text
Parichalak / President
```

Therefore:

```text
UPBS Seva Request / Recommendation
        ↓
UPBS Seva Head
        ↓
Kendra
        ↓
Parichalak / President Approval
        ↓
Approved UPBS Seva Assignment
```

The exact approval implementation shall follow the centralized ERP approval/RBAC framework.

---

# 12. Approval Is Required Before Assignment

A UPBS Seva Assignment shall not become active merely because:

* The person requested it.
* The UPBS Seva Head recommended it.
* The request reached Kendra.

Final approval must be completed by the applicable approval authority.

Therefore:

```text
REQUESTED
    ↓
REVIEWED
    ↓
RECOMMENDED
    ↓
KENDRA APPROVAL
    ↓
APPROVED
    ↓
ACTIVE ASSIGNMENT
```

---

# 13. Rejected UPBS Seva Request

If the request is rejected:

```text
UPBS Seva Request
        ↓
REJECTED
```

the request shall remain in historical records.

It shall not be physically deleted.

The person may request another eligible UPBS Seva Category through a new request.

---

# 14. Multiple UPBS Seva Assignments

A person may have multiple UPBS Seva Assignments where the applicable rules permit.

Example:

```text
Person
 ├── UPBS Seva A → ACTIVE
 ├── UPBS Seva B → ACTIVE
 └── UPBS Seva C → ACTIVE
```

Approval of one UPBS Seva Assignment does not automatically approve another.

Each assignment must follow its applicable workflow.

---

# 15. Assignment Independence

Each UPBS Seva Assignment shall maintain its own:

* Seva Category
* Organizational context
* Request/recommendation
* Approval
* Effective date
* Status
* History
* Audit information

Changing one assignment shall not automatically change another.

---

# 16. UPBS Seva Assignment Status

The UPBS Seva lifecycle shall distinguish between the request/approval lifecycle and the assignment lifecycle.

At the business level, the system must support states equivalent to:

```text
REQUESTED
RECOMMENDED / UNDER REVIEW
APPROVED
ACTIVE
REJECTED
ENDED / INACTIVE
```

The final database status codes shall be finalized during the Seva table-design phase.

---

# 17. Effective Date

An approved UPBS Seva Assignment shall have an effective date.

The effective date represents when the assignment becomes operational.

The following dates shall remain conceptually separate:

```text
Request Date
Approval Date
Effective Date
```

The historical values shall be preserved.

---

# 18. End of UPBS Seva Assignment

When an UPBS Seva Assignment ends:

```text
ACTIVE
   ↓
ENDED / INACTIVE
```

the assignment shall remain in history.

The system shall not physically delete the assignment.

The final end-date and reason model shall be aligned with the common Seva lifecycle and table-design standards.

---

# 19. Membership Transfer

NSS Membership Transfer is authoritative for changing the person's current Sakha.

A Membership Transfer does not constitute a UPBS Seva transfer.

Therefore:

```text
Membership Transfer
        ≠
Automatic UPBS Seva Transfer
```

The person's UPBS Seva history remains preserved.

---

# 20. UPBS Seva After Membership Transfer

An existing UPBS Seva Assignment shall not be automatically deleted merely because the person's NSS Membership has transferred to another Sakha.

The UPBS assignment must be reviewed according to the applicable UPBS/Kendra rules.

Possible outcomes include:

```text
Continue
Modify
End
```

The decision shall be recorded and audited.

---

# 21. No Automatic UPBS Assignment Transfer

The ERP shall not silently convert an existing UPBS Seva Assignment into a new organizational assignment merely because the person's current Sakha changed.

If the organizational context of the UPBS Seva needs to change, the applicable UPBS authority shall review and approve the change.

Historical context must remain preserved.

---

# 22. New UPBS Seva After Membership Transfer

After a Membership Transfer, a person may apply for a new UPBS Seva where eligible.

The new request must follow the applicable UPBS approval process.

Conceptually:

```text
Membership Transfer
        ↓
Current Membership / Sakha Updated
        ↓
Eligibility Re-evaluated
        ↓
New UPBS Seva Request
        ↓
UPBS Seva Head
        ↓
Kendra
        ↓
Parichalak / President
        ↓
New Assignment
```

The new assignment shall not overwrite the old historical assignment.

---

# 23. Sevak Inactivation

When the person's Sevak participation changes:

```text
ACTIVE
   ↓
INACTIVE
```

the person's UPBS Seva Assignment shall not automatically be terminated.

Instead:

```text
Sevak INACTIVE
        ↓
Existing UPBS Seva Assignments
        ↓
Review
```

This is an assignment-level decision.

---

# 24. UPBS Assignment Review After Sevak Inactivation

The applicable UPBS authority shall review active UPBS Seva Assignments.

The review may determine:

```text
Continue
```

or:

```text
End / Inactive
```

The result shall be recorded.

There is no blanket rule:

```text
Sevak INACTIVE
    =
UPBS Seva INACTIVE
```

---

# 25. INACTIVE Sevak With Active UPBS Seva

The following combination is valid:

```text
Sevak Status
    INACTIVE

UPBS Seva Assignment
    ACTIVE
```

provided the applicable authority has reviewed and allowed the assignment to continue.

This preserves the distinction between:

```text
Sevak Participation Status
```

and:

```text
UPBS Seva Assignment Status
```

---

# 26. UPBS Seva and Sevak Sangha Attendance

Attendance at a Sevak Sangha event does not automatically:

* Create UPBS Seva.
* Approve UPBS Seva.
* Reactivate UPBS Seva.
* Change a UPBS Seva Category.
* Create a UPBS Seva Head recommendation.

Similarly:

```text
UPBS Seva Assignment
    ≠
Sevak Sangha Attendance
```

---

# 27. UPBS Seva and Gender

UPBS Seva eligibility is independent of the male-only Sevak Sangha participation rule.

Therefore:

```text
Female Person
    ↓
May undertake UPBS Seva
```

where permitted by the applicable UPBS Seva Category.

Any gender restriction must be explicitly defined by the category/business rule and shall not be inherited from Sevak Sangha participation.

---

# 28. Organizational Scope

UPBS Seva belongs to the UPBS/Kendra organizational context.

The assignment shall preserve the relevant organizational scope.

The system shall not infer organizational scope solely from the person's current Sakha.

Where an assignment is associated with a particular UPBS/Kendra context, that context shall remain explicitly recorded.

---

# 29. Seva Head Responsibilities

The UPBS Seva Head may perform applicable operational functions such as:

* Review requests.
* Review eligibility.
* Recommend suitable persons.
* Submit requests to Kendra.
* Participate in assignment review.
* Recommend continuation or ending of assignments.

The exact permission model shall be governed by centralized RBAC.

---

# 30. Kendra Responsibilities

Kendra is the approval level for UPBS Seva.

Kendra-level processing may include:

* Review of UPBS Seva Head recommendation.
* Verification of eligibility.
* Approval/rejection.
* Assignment review.
* Transfer-related review.
* Inactivation-related review.

The final approval shall be performed by the applicable:

```text
Parichalak / President
```

according to the approved authority framework.

---

# 31. Approval Audit

Every UPBS approval shall preserve:

* Request
* Recommendation
* Reviewer
* Approver
* Decision
* Decision timestamp
* Effective date
* Assignment status
* Audit trail

Approval history shall not be overwritten.

---

# 32. No Self-Approval

A requester shall not approve their own UPBS Seva request.

The ERP approval workflow shall enforce separation between:

```text
Requester
```

and:

```text
Approver
```

where the applicable approval framework requires it.

---

# 33. Historical Preservation

The following shall remain historically available:

* UPBS Seva requests
* Recommendations
* Rejections
* Approvals
* Assignments
* Assignment changes
* Membership Transfer review
* Sevak Inactivation review
* Ended assignments

Historical records shall not be physically deleted.

---

# 34. UPBS Seva Workflow

### Sevak-requested

```text
Eligible Person / Sevak
        ↓
UPBS Seva Request
        ↓
UPBS Seva Head Review
        ↓
Kendra Submission
        ↓
Parichalak / President
        ↓
Approved
        ↓
UPBS Seva Assignment
```

### UPBS Seva Head recommendation

```text
UPBS Seva Head
        ↓
Recommendation
        ↓
Kendra
        ↓
Parichalak / President
        ↓
Approved
        ↓
UPBS Seva Assignment
```

---

# 35. Membership Transfer Workflow

```text
NSS Membership Transfer
        ↓
Current Sakha Updated
        ↓
Existing UPBS Seva Preserved
        ↓
UPBS Review if Required
        ├── Continue
        ├── Modify
        └── End
```

A new UPBS Seva request follows the normal UPBS approval process.

---

# 36. Sevak Inactivation Workflow

```text
Sevak ACTIVE
        ↓
Sevak INACTIVE
        ↓
Identify Active UPBS Assignments
        ↓
UPBS Review
        ├── Continue
        └── End / Inactive
```

No automatic blanket termination shall occur.

---

# 37. Relationship With General Seva Rules

General Seva principles are maintained in:

```text
01_seva_business_rules.md
```

This document supplements those rules with UPBS-specific requirements.

Where a general Seva rule and an explicitly defined UPBS rule appear to overlap, the UPBS-specific workflow shall govern the UPBS context.

---

# 38. Relationship With Sakha Seva

Regular Sakha Seva follows:

```text
Seva Head
    ↓
Sakha President
```

UPBS Seva follows:

```text
UPBS Seva Head
    ↓
Kendra
    ↓
Parichalak / President
```

These approval chains shall not be merged.

---

# 39. Relationship With Sevak Sangha Events

The following remain separate:

```text
Sakha-Level Sevak Sangha Session
        ≠
Anchalika/Zilla Sevak Sangha Puja
        ≠
UPBS Seva
```

Attendance at either Sevak Sangha event does not itself create or approve UPBS Seva.

---

# 40. Audit and History

The following actions shall be auditable:

* UPBS Seva request
* UPBS Seva Head review
* Recommendation
* Kendra submission
* Approval
* Rejection
* Assignment creation
* Assignment activation
* Assignment modification
* Membership Transfer review
* Sevak Inactivation review
* Assignment continuation
* Assignment ending

Historical records shall be retained according to the ERP audit and retention standards.

---

# 41. No Physical Deletion

Historical UPBS Seva records shall not be physically deleted because:

* A request was rejected.
* An assignment ended.
* Membership transferred Sakha.
* Sevak status became INACTIVE.
* A Seva Category was retired.
* An assignment was modified.

The system shall preserve historical accountability.

---

# 42. Frozen Principles

The following principles are approved for UPBS Seva:

* UPBS Seva is part of the overall Seva framework.
* UPBS Seva is separate from Sevak Sangha participation.
* UPBS Seva Categories are master-data driven.
* UPBS Seva eligibility is category-driven.
* UPBS Seva is not subject to the male-only Sevak Sangha participation rule.
* Male and Female persons may undertake UPBS Seva where permitted by the applicable category.
* A UPBS Seva request is separate from an approved assignment.
* A UPBS Seva Head may review and recommend Seva.
* UPBS Seva Head review precedes Kendra approval.
* Final approval is at Kendra level through the applicable Parichalak / President authority.
* A request or recommendation does not itself create an active assignment.
* Rejected requests remain in history.
* A person may have multiple UPBS Seva Assignments where permitted.
* Each UPBS assignment has an independent lifecycle.
* Membership Transfer does not automatically delete UPBS Seva history.
* Membership Transfer does not automatically transfer a UPBS Seva Assignment.
* Existing UPBS Seva may require review after Membership Transfer.
* A new UPBS Seva Assignment requires the applicable approval process.
* Sevak INACTIVE status does not automatically terminate UPBS Seva.
* Active UPBS Seva may continue after Sevak inactivation when approved by the applicable authority.
* Inactivation triggers review of applicable active UPBS Seva Assignments.
* UPBS Seva and Sevak Sangha attendance are independent.
* No self-approval is permitted where separation of requester and approver is required.
* All UPBS Seva workflows are auditable.
* Historical UPBS Seva records are never physically deleted.

---

# 43. Related Documents

```text
../01_sevak_module_overview.md
../03_sevak_lifecycle.md
../04_sevak_participation_rules.md
../05_sevak_business_rules.md
../06_sevak_table_design.md

../sangha/01_sakha_sevak_sangha_session_rules.md
../sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md

01_seva_business_rules.md

../events/01_other_sevak_event_rules.md

../../administration/
../../membership/
../../attendance/
../../reports/
```

---

# End of Document
