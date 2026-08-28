# NSS ERP Attendance Table Design

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Attendance Table Design |
| Document ID | SOL-ATT-004 |
| Domain | Attendance |
| Repository Path | docs/03_Solution/modules/attendance/04_attendance_table_design.md |
| Version | 1.0.0 |
| Status | DRAFT |
| Parent Document | 01_attendance_module_overview.md |

---

# 1. Purpose

This document defines the logical PostgreSQL table design for the NSS ERP Attendance Module.

---

# 2. Attendance Table Set

The core Attendance tables are:

```text
weekly_sangha_puja

weekly_sangha_puja_attendance

attendance_exception

attendance_review
```

---

# 3. weekly_sangha_puja

## Purpose

Stores an individual Weekly Sangha Puja attendance event.

---

## Main Columns

```text
weekly_sangha_puja_pk

sakha_pk

puja_date

remarks

created_at

updated_at
```

---

## Key Rules

```text
weekly_sangha_puja_pk
    PRIMARY KEY

sakha_pk
    FOREIGN KEY

puja_date
    NOT NULL
```

---

# 4. weekly_sangha_puja_attendance

## Purpose

Stores attendance for an individual Weekly Sangha Puja.

---

## Main Columns

```text
attendance_pk

weekly_sangha_puja_pk

sangha_sevi_pk

attendance_status

attendance_sakha_pk

remarks

created_at

updated_at
```

---

# 5. Attendance Status

The controlled Attendance Status values are:

```text
PRESENT

ABSENT

EXCUSED_ABSENCE
```

---

# 6. Attendance Identity

The attendance record shall reference:

```text
sangha_sevi_pk
```

where the attendee is an NSS Member.

This links Attendance to the authoritative Membership identity.

---

# 7. Attendance Sakha

The attendance record shall preserve the Sakha where attendance was actually recorded.

```text
attendance_sakha_pk
```

This supports the cross-Sakha attendance model.

---

# 8. Home Sakha

The Member's current/home Sakha remains determined from the Membership/Organization relationship.

The Attendance record does not overwrite the Membership organization.

Therefore:

```text
Membership Organization
        is not equal to
Attendance Organization
```

when a Member attends another Sakha.

---

# 9. Attendance Uniqueness

For a normal Weekly Sangha Puja attendance event, a Member should have one attendance record for that event.

Logical uniqueness:

```text
weekly_sangha_puja_pk
+
sangha_sevi_pk
```

---

# 10. attendance_exception

## Purpose

Stores approved attendance exceptions.

---

## Main Columns

```text
exception_pk

sangha_sevi_pk

exception_type

from_date

to_date

approved_by

approved_date

remarks

created_at

updated_at
```

---

# 11. Exception Type

Exception types shall be controlled through master data.

The exact catalogue may be extended through approved project governance.

---

# 12. attendance_review

## Purpose

Stores the Attendance Review created after the applicable consecutive-absence condition is reached.

---

## Main Columns

```text
review_pk

sangha_sevi_pk

trigger_date

consecutive_absences

review_status

assigned_to_role

closed_by_sangha_sevi_pk

deferred_by_sangha_sevi_pk

escalated_by_sangha_sevi_pk

remarks

created_at

updated_at
```

---

# 13. Review Status

The Review Status master supports:

```text
OPEN

DEFERRED

CLOSED

ESCALATED_TO_PRESIDENT

ESCALATED_TO_PARICHALAK
```

---

# 14. Review Authority

The assigned_to_role field identifies the operational role responsible for the review.

The primary operational authority is:

```text
SECRETARY
```

Escalation may involve:

```text
PRESIDENT
PARICHALAK
```

---

# 15. Review Trigger

The Attendance Review trigger is:

```text
Three Consecutive Weekly Sangha Puja Absences
```

The review record shall preserve:

```text
trigger_date

consecutive_absences
```

---

# 16. Review Audit

The review table shall preserve responsible actions.

Examples:

```text
closed_by_sangha_sevi_pk

deferred_by_sangha_sevi_pk

escalated_by_sangha_sevi_pk
```

---

# 17. Attendance Status Master

Attendance Status shall be master-data driven.

Official values:

```text
PRESENT

ABSENT

EXCUSED_ABSENCE
```

---

# 18. Review Status Master

Review Status shall be master-data driven.

Values:

```text
OPEN

DEFERRED

CLOSED

ESCALATED_TO_PRESIDENT

ESCALATED_TO_PARICHALAK
```

---

# 19. Primary Key Standard

Attendance transactional tables shall use internal UUID primary keys.

Examples:

```text
weekly_sangha_puja_pk

attendance_pk

exception_pk

review_pk
```

---

# 20. Foreign Key Standard

Foreign keys shall reference internal primary keys.

Examples:

```text
sakha_pk

weekly_sangha_puja_pk

sangha_sevi_pk

attendance_sakha_pk
```

---

# 21. Audit Columns

Applicable Attendance tables shall preserve:

```text
created_at

created_by

updated_at

updated_by
```

Review records shall preserve the responsible actor for review actions.

---

# 22. History

Attendance records shall not be physically deleted.

Attendance Review history shall not be physically deleted.

---

# 23. Membership Boundary

The Attendance schema shall not duplicate:

```text
Membership Type

Membership Status

Sangha Sevi ID generation

Membership Transfer

Membership Renewal
```

Those remain owned by the Membership Module.

---

# 24. Cross-Sakha Boundary

The Attendance schema shall support:

```text
Member Home Sakha
```

and:

```text
Attendance Sakha
```

as separate concepts.

---

# 25. Final Attendance Table Set

```text
weekly_sangha_puja

weekly_sangha_puja_attendance

attendance_exception

attendance_review
```

---

# 26. Database Principles

```text
Attendance Is Event Based

Membership Identity Is Authoritative

Attendance Sakha Is Preserved

Cross-Sakha Attendance Does Not Transfer Membership

Attendance Status Is Master Data Driven

Review Status Is Master Data Driven

Human Review Before Membership Action

History Never Deleted

Auditability
```

---

# End of Document
