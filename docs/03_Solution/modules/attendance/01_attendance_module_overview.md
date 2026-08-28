# NSS ERP Attendance Module Overview

Version: 1.0

Status: DRAFT

---

# 1. Purpose

The Attendance Module manages NSS attendance for Weekly Sangha Puja, attendance exceptions, attendance monitoring, attendance alerts, and Attendance Review workflows.

The module provides the attendance information required for Membership monitoring while keeping Membership lifecycle decisions within the Membership Module.

---

# 2. Core Principle

Attendance is an operational record.

Attendance does not itself change Membership status.

The system shall record attendance accurately and shall create a review workflow when the applicable attendance condition is reached.

---

# 3. Primary Attendance Source

The primary Membership-related attendance source is:

```text
Weekly Sangha Puja
```

The Attendance Module therefore records attendance for Weekly Sangha Puja at the Sakha level.

---

# 4. Attendance Identity

Attendance shall be linked to the person's authoritative Membership identity where the attendee is a Member.

The primary Membership identity is:

```text
Sangha Sevi ID
```

Example:

```text
SS00000001
SS00000002
SS00000003
```

The Attendance Module shall not create a second Membership identity.

---

# 5. Attendance Status

The Attendance Module supports the following attendance statuses:

```text
PRESENT
ABSENT
EXCUSED_ABSENCE
```

The status values shall be controlled through master data.

---

# 6. Attendance Recording

Attendance shall be recorded against a specific Weekly Sangha Puja occurrence.

Relationship:

```text
Weekly Sangha Puja
        |
Attendance Record
        |
Person / Membership
```

Each attendance record identifies:

* Attendance event
* Person / Membership
* Attendance status
* Remarks where applicable
* Audit information

---

# 7. Weekly Sangha Puja

A Weekly Sangha Puja attendance event is associated with a Sakha.

Example:

```text
Sakha
    |
Weekly Sangha Puja
    |
Attendance
```

The attendance record shall preserve the Sakha where the attendance was recorded.

---

# 8. Excused Absence

An approved absence may be recorded as:

```text
EXCUSED_ABSENCE
```

An Excused Absence shall not be treated as an ordinary absence for consecutive-absence monitoring.

The applicable exception approval shall be preserved.

---

# 9. Consecutive Absence Monitoring

The Attendance Module shall monitor consecutive Weekly Sangha Puja absences.

The statutory rule recognizes three consecutive weekly Sangha Puja absences as a ground for Membership review.

The ERP shall therefore detect:

```text
ABSENT
ABSENT
ABSENT
```

and create the appropriate Attendance Review workflow.

---

# 10. No Automatic Membership Action

Three consecutive absences shall not automatically:

* Suspend Membership
* Cancel Membership
* Revoke Parichaya Patra
* Delete Membership

The system creates an Attendance Review.

Membership action requires human review and an authorized decision.

---

# 11. Attendance Review

Attendance Review is a controlled workflow.

The frozen operational authority is:

```text
Secretary
    |
Primary Operational Authority
```

with:

```text
President
    |
Oversight / Appeal Authority
```

---

# 12. Attendance Review Outcomes

An Attendance Review may be:

```text
OPEN

DEFERRED

CLOSED

ESCALATED_TO_PRESIDENT

ESCALATED_TO_PARICHALAK
```

These values are controlled review statuses.

---

# 13. Secretary Responsibilities

The Secretary may:

* Create Attendance Review
* Review Attendance History
* Contact Member / Family
* Record Explanation
* Approve Excused Absence
* Defer Review
* Close Review
* Escalate to President

---

# 14. President Responsibilities

The President may:

* View Attendance Reviews
* Review Secretary Decisions
* Intervene in Sensitive Cases
* Override Decisions
* Reopen Closed Reviews
* Escalate to Parichalak

---

# 15. Attendance Review and Membership

Attendance Review is separate from Membership status.

Relationship:

```text
Attendance
    |
Attendance Alert / Review
    |
Human Review
    |
Possible Membership Action
```

Membership status remains unchanged until an authorized Membership decision is made.

---

# 16. Darshak Operational Attendance

Darshak is not an official Membership Type.

The approved operational Darshak rule permits the term to be used in Attendance/UI contexts.

Operational Darshak may include:

```text
Probationary Member
```

or:

```text
Regular Member of another Sakha
```

The authoritative operational rule is maintained separately in:

```text
DARSHAK_BUSINESS_RULE.md
```

The database Membership Type remains:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

---

# 17. Cross-Sakha Attendance

A Regular Member may attend a Weekly Sangha Puja at another Sakha without transferring Membership.

The Attendance Module shall preserve:

```text
Membership / Home Sakha
        is not equal to
Attendance Sakha
```

where applicable.

The attendance event shall identify the Sakha at which attendance was actually recorded.

The member remains a Regular Member of the home Sakha unless a formal Membership Transfer occurs.

---

# 18. Attendance and Membership Enforcement

Attendance is one input into Membership monitoring.

The Attendance Module does not own:

* Membership Type
* Membership Status
* Sangha Sevi ID lifecycle
* Membership transfer
* Membership renewal
* Membership reinstatement

Those remain owned by the Membership Module.

---

# 19. Attendance History

Attendance history shall never be physically deleted.

Historical attendance must remain available for:

* Membership review
* Reporting
* Audit
* Attendance statistics
* Sakha monitoring
* Kendra reporting

---

# 20. Audit Principles

Attendance actions shall preserve applicable:

* Created By
* Created At
* Updated By
* Updated At
* Historical Traceability

Attendance Review actions shall also preserve the responsible authority and action history.

---

# 21. Module Dependencies

```text
Foundation
    |
Person
    |
Organization
    |
Membership
    |
Attendance
    |
Attendance Review
```

Attendance also interacts with:

```text
Family
Governance
Reports
Administration
```

---

# 22. Frozen Decisions

* Weekly Sangha Puja is the primary Membership attendance source.
* Attendance is linked to Membership identity.
* Attendance statuses are PRESENT, ABSENT and EXCUSED_ABSENCE.
* Excused Absence does not count as ordinary absence.
* Three consecutive absences create an Attendance Review.
* Three absences do not automatically change Membership status.
* Secretary is the primary operational Attendance Review authority.
* President has oversight and appeal authority.
* Review history is preserved.
* Attendance history is never physically deleted.
* Darshak is an operational/UI term, not a Membership Type.
* Cross-Sakha attendance shall preserve the actual Attendance Sakha separately from the Member's home Sakha.

---

# 23. Summary

The Attendance Module provides the authoritative ERP record of Weekly Sangha Puja attendance and the operational Attendance Review workflow.

It is the authoritative source for:

* Weekly Sangha Puja Attendance
* Attendance Status
* Attendance Exceptions
* Consecutive Absence Monitoring
* Attendance Alerts
* Attendance Review
* Attendance Review History

Membership decisions remain under the Membership Module.

---

# End of Document
