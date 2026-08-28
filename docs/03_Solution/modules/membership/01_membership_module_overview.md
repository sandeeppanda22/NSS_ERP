# NSS ERP Membership Module Overview

Version: 1.0

Status: DRAFT

---

# 1. Purpose

The Membership Module manages NSS Membership identities, membership lifecycle, membership status, transfers, renewals, attendance-related reviews, and governance eligibility foundations.

The module is built on top of the Person Module.

---

# 2. Core Principle

Person ≠ Member

A Person may exist without Membership.

A Membership must always belong to a Person.

Membership cannot exist independently.

Examples of Persons without Membership:

* Family Members
* Kumari Participants
* Kishor Participants
* Guardians
* Guests
* Historical Persons

---

# 3. Membership Identity

Membership identity is represented by the Sangha Sevi ID.

Example:

```text
SS00000001
SS00000002
SS00000003
```

Rules:

* System Generated
* Globally Unique
* Permanent
* Never Reused
* Never Changed

---

# 4. One Person One Membership Rule

Frozen Principle:

```text
One Person
    ↓
One Membership
    ↓
One Sangha Sevi ID
```

Rules:

* One Person can have only one Membership.
* One Membership belongs to exactly one Person.
* One Person can have only one Sangha Sevi ID.

---

# 5. Membership Types

The Membership Module supports the following membership types:

## Probationary Member

Entry-level membership.

Subject to review and evaluation.

---

## Regular Member

Full membership status.

Eligible for governance participation subject to NSS rules.

---

## Associate Member

Special membership category.

Governance eligibility determined by NSS policy.

---

# 6. Membership Sources

Membership may originate through:

* Direct Application
* Kumari Transition
* Kishor Transition
* Administrative Entry
* Historical Data Migration

---

# 7. Membership Lifecycle

Typical lifecycle:

```text
Applicant
    ↓
Probationary Member
    ↓
Regular Member
```

Alternative lifecycle:

```text
Applicant
    ↓
Associate Member
```

Detailed lifecycle rules are maintained in:

```text
03_membership_lifecycle.md
```

---

# 8. Membership Status

Membership status is maintained independently of membership type.

Examples:

* ACTIVE
* RENEWAL_PENDING
* EXPIRED
* SUSPENDED
* ON_HOLD
* DISCIPLINARY_REVIEW
* TRANSFERRED
* DECEASED

Managed through:

```text
membership_status_master
```

---

# 9. Relationship With Person Module

The Membership Module depends on the Person Module.

Relationship:

```text
Person
    ↓
Membership
```

Rules:

* Membership cannot exist without a Person.
* Person records may exist without Membership.
* Membership inherits identity information from Person.

---

# 10. Relationship With Family Module

Family relationships are not maintained by Membership.

Examples:

* Father
* Mother
* Husband
* Wife
* Child

These belong to the Family Module.

---

# 11. Relationship With Governance Module

Membership provides eligibility foundations.

Membership alone does not grant governance authority.

Governance eligibility is controlled by Governance rules.

---

# 12. Relationship With Attendance Module

Attendance affects reviews and membership monitoring.

Attendance alone does not automatically:

* Suspend Membership
* Cancel Membership

Human review is always required.

---

# 13. Membership Transfer

Transfers are supported between Sakhas.

Rules:

* Sangha Sevi ID remains unchanged.
* Local Sakha Number may change.
* Transfer history preserved permanently.
* Effective date follows NSS policy.

---

# 14. Membership Renewal

Membership renewal is supported.

Rules:

* Renewal history preserved.
* Sangha Sevi ID remains unchanged.
* Membership identity remains permanent.

---

# 15. Audit Principles

All membership actions must preserve:

* Created By
* Updated By
* Timestamp
* Historical Traceability

Audit history must never be deleted.

---

# 16. Deletion Principles

Physical deletion is prohibited.

Membership history is permanent.

Only status transitions are allowed.

---

# 17. Future Expansion

Future Membership enhancements may include:

* Membership Reinstatement
* Disciplinary Workflow
* Advanced Eligibility Rules
* Membership Scoring
* Digital Membership Cards

---

# 18. Frozen Decisions

* Person ≠ Member
* One Person = One Membership
* One Membership = One Sangha Sevi ID
* Sangha Sevi ID Permanent
* Sangha Sevi ID Never Reused
* Transfer Does Not Change Sangha Sevi ID
* Membership History Never Deleted
* Physical Delete Prohibited
* Attendance Review Required Before Membership Action

---

# 19. Module Dependencies

```text
Foundation
    ↓
Person
    ↓
Membership
    ↓
Family
    ↓
Governance
    ↓
Attendance
```

---

# 20. Summary

The Membership Module provides the official NSS Membership identity and lifecycle management system.

It is the authoritative source for:

* Sangha Sevi ID
* Membership Type
* Membership Status
* Membership Lifecycle
* Transfers
* Renewals
* Membership Audit History
