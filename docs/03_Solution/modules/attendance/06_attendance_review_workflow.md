# NSS ERP Attendance Review Workflow

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Attendance Review Workflow |
| Document ID | SOL-ATT-005 |
| Domain | Attendance |
| Repository Path | docs/03_Solution/modules/attendance/05_attendance_review_workflow.md |
| Version | 1.0.0 |
| Status | FROZEN |
| Parent Document | 01_attendance_module_overview.md |

---

# 1. Purpose

This document defines the frozen operational workflow for Attendance Review in the NSS ERP.

---

# 2. Review Trigger

Attendance Review is triggered when the system detects:

```text
Three Consecutive Weekly Sangha Puja Absences
```

Example:

```text
Week 1 — ABSENT
Week 2 — ABSENT
Week 3 — ABSENT
```

The system creates an Attendance Review.

---

# 3. Review Does Not Automatically Change Membership

The Attendance Review is a human review process.

The system shall not automatically:

```text
Suspend Membership

Cancel Membership

Terminate Membership

Revoke Parichaya Patra

Revoke Anumati Patra
```

The Membership remains unchanged until an authorized decision is taken.

---

# 4. Review Creation

When the trigger is reached:

```text
Three Consecutive Absences
        |
Attendance Review Created
        |
Review Status = OPEN
        |
Secretary Review
```

---

# 5. Secretary as Primary Authority

The Secretary is the primary operational authority.

The Secretary may:

```text
Create Attendance Review

Review Attendance History

Contact Member / Family

Record Explanation

Approve Excused Absence

Defer Review

Close Review

Escalate to President
```

---

# 6. Review Examination

The Secretary should review:

```text
Attendance History

Attendance Exceptions

Member Explanation

Relevant Family Information

Previous Attendance Reviews

Available Supporting Information
```

The review must remain within the authority of the Secretary.

---

# 7. Possible Secretary Outcomes

The Secretary may:

```text
Close Review
```

or:

```text
Defer Review
```

or:

```text
Escalate to President
```

---

# 8. Close Review

Workflow:

```text
OPEN
  |
Secretary Review
  |
CLOSED
```

The closure action shall preserve:

```text
Closed By

Closed Date

Remarks
```

---

# 9. Defer Review

Workflow:

```text
OPEN
  |
Secretary Review
  |
DEFERRED
```

A deferred review remains available for later action.

The deferral shall preserve:

```text
Deferred By

Deferred Date

Reason / Remarks
```

---

# 10. Escalate to President

Workflow:

```text
OPEN
  |
Secretary Review
  |
ESCALATED_TO_PRESIDENT
  |
President Review
```

---

# 11. President Authority

The President may:

```text
View All Attendance Reviews

Review Secretary Decisions

Intervene in Sensitive Cases

Override Decisions

Reopen Closed Reviews

Escalate to Parichalak
```

---

# 12. President Override

Where the President overrides a Secretary decision, the system shall preserve:

```text
Previous Decision

President Decision

Reason

Decision Date

President Identity
```

The original Secretary action must remain historically traceable.

---

# 13. Reopen Closed Review

A Secretary cannot reopen a closed review.

The President may reopen a closed review.

Workflow:

```text
CLOSED
  |
President
  |
REOPEN
  |
OPEN
```

The reopening action must be audited.

---

# 14. Escalation to Parichalak

Where the matter requires higher authority:

```text
President
    |
ESCALATED_TO_PARICHALAK
    |
Parichalak
```

The Parichalak may then handle the matter according to applicable Membership and governance rules.

---

# 15. Review Statuses

The frozen status values are:

```text
OPEN

DEFERRED

CLOSED

ESCALATED_TO_PRESIDENT

ESCALATED_TO_PARICHALAK
```

---

# 16. Authority Matrix

| Action                  | Secretary | President |
| ----------------------- | --------: | --------: |
| Create Review           |       Yes |       Yes |
| View Review             |       Yes |       Yes |
| Approve Excused Absence |       Yes |       Yes |
| Defer Review            |       Yes |       Yes |
| Close Review            |       Yes |       Yes |
| Reopen Closed Review    |        No |       Yes |
| Override Decision       |        No |       Yes |
| Escalate to Parichalak  |        No |       Yes |

This authority matrix is frozen in the project Attendance Review decision.

---

# 17. Excused Absence During Review

If a valid explanation or supporting information establishes an approved absence, the Secretary or President may approve an Excused Absence according to authority.

The Attendance record shall remain historically traceable.

The system shall not erase the original attendance event.

---

# 18. Review and Membership Action

If the Attendance Review results in a Membership concern requiring action:

```text
Attendance Review
        |
Authorized Decision
        |
Membership Workflow
        |
Membership Action
```

The Attendance Module shall not directly perform Membership lifecycle changes outside the approved Membership workflow.

---

# 19. Review History

Every review shall maintain an auditable history.

The system shall preserve:

```text
Review Created

Review Assigned

Explanation Recorded

Exception Approved

Review Deferred

Review Closed

Review Reopened

Review Overridden

Review Escalated
```

---

# 20. Cross-Sakha Attendance During Review

If the Member has attendance at another Sakha, the reviewer shall be able to see the actual Attendance Sakha.

Example:

```text
Home Sakha:
Sakha A

Attendance:
Sakha B

Operational Category:
Other Sakha / Darshak
```

Attendance at Sakha B must not be incorrectly treated as a Membership transfer to Sakha B.

---

# 21. Reporting

The Attendance Review Dashboard shall support:

```text
Open Reviews

Deferred Reviews

Closed Reviews

President Escalations

Parichalak Escalations

Consecutive Absence Watch List
```

---

# 22. Sakha Dashboard

The Sakha Dashboard may display:

```text
Attendance percentage

Watch List

Attendance Reviews

Deferred Reviews
```

---

# 23. Kendra Dashboard

The Kendra Dashboard may display aggregated:

```text
Attendance Reviews

Deferred Reviews

Watch List
```

The Kendra dashboard is an aggregate operational view and does not replace Sakha-level review authority.

---

# 24. No Automatic Termination

The Attendance Review workflow shall never directly execute:

```text
DELETE Membership
```

or:

```text
AUTOMATICALLY TERMINATE Membership
```

Membership action requires the appropriate authorized Membership workflow.

---

# 25. Frozen Workflow

```text
Weekly Sangha Puja
        |
Attendance Recorded
        |
Consecutive Absence Monitoring
        |
3 Consecutive Absences
        |
Attendance Review
        |
Secretary Review
        |
        +-- Close
        |
        +-- Defer
        |
        +-- Escalate to President
                    |
              President Review
                    |
                    +-- Close
                    |
                    +-- Reopen
                    |
                    +-- Override
                    |
                    +-- Escalate to Parichalak
```

---

# 26. Frozen Principles

```text
Secretary = Primary Operational Authority

President = Oversight / Appeal Authority

Parichalak = Higher Escalation Authority

Three Consecutive Absences = Review Trigger

Review does not equal Automatic Membership Action

History Never Deleted

All Review Actions Audited
```

---

# End of Document
