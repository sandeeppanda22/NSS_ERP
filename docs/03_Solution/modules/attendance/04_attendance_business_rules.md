# NSS ERP Attendance Business Rules

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Attendance Business Rules |
| Document ID | SOL-ATT-003 |
| Domain | Attendance |
| Repository Path | docs/03_Solution/modules/attendance/03_attendance_business_rules.md |
| Version | 1.0.0 |
| Status | DRAFT |
| Parent Document | 01_attendance_module_overview.md |

---

# 1. Purpose

This document defines the business rules governing Attendance and Attendance Review in the NSS ERP.

---

# 2. Attendance Identity Rules

## ATT-001 — Attendance Identity

Attendance shall be linked to the authoritative Person/Membership identity.

For a Member, the primary business identity is the Sangha Sevi ID.

---

## ATT-002 — No Duplicate Membership Identity

Attendance shall not create a new Membership identity for an existing Member.

---

# 3. Weekly Sangha Puja Rules

## ATT-003 — Primary Attendance Source

Weekly Sangha Puja is the primary Membership-related attendance source.

---

## ATT-004 — Sakha Attendance Event

Each Weekly Sangha Puja attendance event shall identify the Sakha at which the Puja was conducted.

---

## ATT-005 — Attendance Date

Each Weekly Sangha Puja shall have a defined Puja date.

---

# 4. Attendance Status Rules

## ATT-006 — PRESENT

PRESENT indicates that the Member/attendee attended the Weekly Sangha Puja.

---

## ATT-007 — ABSENT

ABSENT indicates that the Member did not attend the relevant Weekly Sangha Puja and no approved exception applies.

Only ABSENT contributes to consecutive-absence monitoring.

---

## ATT-008 — EXCUSED_ABSENCE

EXCUSED_ABSENCE indicates an approved attendance exception.

An Excused Absence shall not increment the consecutive-absence counter.

---

# 5. Consecutive Absence Rules

## ATT-009 — Consecutive Absence Monitoring

The system shall monitor consecutive Weekly Sangha Puja absences.

Example:

```text
Week 1 — ABSENT
Week 2 — ABSENT
Week 3 — ABSENT
```

This reaches the Attendance Review trigger.

---

## ATT-010 — Three Consecutive Absences

Three consecutive Weekly Sangha Puja absences shall create an Attendance Review.

This reflects the statutory Membership provision concerning absence from three consecutive Weekly Sangha Pujas.

---

## ATT-011 — No Automatic Suspension

Three consecutive absences shall not automatically suspend Membership.

---

## ATT-012 — No Automatic Cancellation

Three consecutive absences shall not automatically cancel or terminate Membership.

---

## ATT-013 — No Automatic Identity Document Revocation

Attendance shall not automatically revoke:

```text
Parichaya Patra

Anumati Patra
```

---

# 6. Attendance Review Rules

## ATT-014 — Review Creation

When the three-consecutive-absence condition is reached, the ERP shall create an Attendance Review.

---

## ATT-015 — Secretary Primary Authority

The Secretary is the primary operational authority for Attendance Review.

The Secretary may:

* Create Review
* Review Attendance History
* Contact Member / Family
* Record Explanation
* Approve Excused Absence
* Defer Review
* Close Review
* Escalate to President

---

## ATT-016 — President Oversight

The President may:

* View Attendance Reviews
* Review Secretary Decisions
* Intervene in Sensitive Cases
* Override Decisions
* Reopen Closed Reviews
* Escalate to Parichalak

---

## ATT-017 — Parichalak Escalation

The Parichalak may become involved when a Membership decision or higher-level authority is required.

---

# 7. Attendance Review Status

## ATT-018 — Review Status Values

The Attendance Review Status master shall support:

```text
OPEN

DEFERRED

CLOSED

ESCALATED_TO_PRESIDENT

ESCALATED_TO_PARICHALAK
```

---

## ATT-019 — Open Review

An OPEN review requires action by the assigned operational authority.

---

## ATT-020 — Deferred Review

A DEFERRED review remains unresolved and may be revisited.

---

## ATT-021 — Closed Review

A CLOSED review has completed its operational review process.

---

## ATT-022 — Escalated Review

An ESCALATED_TO_PRESIDENT review requires President-level intervention.

An ESCALATED_TO_PARICHALAK review requires Parichalak-level intervention.

---

# 8. Review Authority Matrix

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

This authority matrix is frozen.

---

# 9. Attendance Exception Rules

## ATT-023 — Exception Recording

Approved attendance exceptions shall be recorded separately from ordinary Attendance Status.

---

## ATT-024 — Exception Period

An Attendance Exception may apply to a defined period.

The system shall preserve:

```text
From Date

To Date

Exception Type

Approving Authority

Remarks
```

---

## ATT-025 — Exception Effect

Where an approved exception applies to a Weekly Sangha Puja, the relevant absence shall not be treated as an ordinary ABSENT for consecutive-absence monitoring.

---

# 10. Cross-Sakha Attendance

## ATT-026 — Cross-Sakha Attendance

A Member may attend a Weekly Sangha Puja at another Sakha without transferring Membership.

The Attendance record shall identify the actual Sakha where the Member attended.

---

## ATT-027 — Membership Home Sakha

The Member's Membership remains associated with the Member's current/home Sakha unless a formal Membership Transfer occurs.

---

## ATT-028 — Attendance Sakha

The Sakha where the Weekly Sangha Puja was actually attended shall be stored as the Attendance Sakha.

---

## ATT-029 — Operational Darshak

A Regular Member of another Sakha attending a Sakha without transferring Membership may be displayed operationally as:

```text
Darshak
Type: Other Sakha
```

The authoritative Membership Type remains:

```text
REGULAR
```

---

## ATT-030 — Probationary Darshak

A Probationary Member attending the Weekly Sangha Puja may be displayed operationally as:

```text
Darshak
Type: Probationary
```

The authoritative Membership Type remains:

```text
PROBATIONARY
```

The detailed operational rule is maintained in:

```text
DARSHAK_BUSINESS_RULE.md
```

---

# 11. Attendance and Membership Action

## ATT-035 — Human Review Required

Attendance Review must be completed by an authorized human authority before Membership action is taken.

---

## ATT-036 — Membership Status Ownership

Membership status is owned by the Membership Module.

Attendance shall not directly update Membership status without the appropriate Membership workflow.

---

# 12. Audit Rules

## ATT-037 — Attendance Audit

Attendance creation and modification shall preserve applicable audit information.

---

## ATT-038 — Review Audit

Attendance Review actions shall preserve:

```text
Actor

Action

Date / Time

Previous Status

New Status

Remarks
```

---

# 13. History Rules

## ATT-039 — Attendance History

Attendance records shall not be physically deleted.

---

## ATT-040 — Review History

Attendance Review history shall remain traceable.

---

# 14. Frozen Attendance Principles

```text
Weekly Sangha Puja Is the Primary Attendance Source

PRESENT / ABSENT / EXCUSED_ABSENCE

Only ABSENT Counts Toward Consecutive Absence

Three Consecutive Absences Create Attendance Review

Three Absences Do Not Automatically Suspend Membership

Three Absences Do Not Automatically Cancel Membership

Secretary Is Primary Operational Review Authority

President Has Oversight and Appeal Authority

Attendance Sakha Is Separate From Home Sakha for Cross-Sakha Attendance

Darshak Is an Operational/UI Concept Only

Membership Type Remains PROBATIONARY / REGULAR / ASSOCIATE

History Never Deleted
```

---

# 15. Authority Hierarchy

Attendance implementation shall follow:

```text
NSS Bye-Law / Authoritative Reference
        |
Approved Governance Decision
        |
Approved Attendance Business Rule
        |
Solution Design
        |
Implementation
```

---

# End of Document
