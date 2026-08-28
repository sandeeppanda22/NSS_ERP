# NSS ERP — Membership Lifecycle

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Membership Lifecycle |
| Document ID | SOL-MEM-003 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/03_membership_lifecycle.md |
| Version | 1.0.0 |
| Status | Draft |
| Authority | NSS ERP Membership Module |
| Parent Document | 01_membership_module_overview.md |
| Related Documents | 02_membership_erd.md, 04_membership_business_rules.md, 05_membership_table_design.md |
| Effective Date | TBD |

---

# 1. Purpose

This document defines the Membership lifecycle implemented by the NSS ERP.

The lifecycle distinguishes:

- Person.
- Applicant.
- Membership.
- Membership Type.
- Membership Status.
- Renewal.
- Transfer.
- Probationary progression.
- Identity documents.
- Membership review.
- Historical events.

---

# 2. Person to Membership

A Person may exist without Membership.

Examples include:

- Family Members.
- Kumari Participants.
- Kishor Participants.
- Guardians.
- Guests.
- Historical Persons.

Therefore:

```text
Person
   |
May become Member
```

Membership cannot exist independently of a Person.

---

# 3. Membership Identity Creation

When a Person is approved for Membership:

```text
Person
   |
Membership Approved
   |
Sangha Sevi record created
   |
Sangha Sevi ID generated
```

Example:

```text
Person
   |
SS00000001
```

The Sangha Sevi ID is permanent.

---

# 4. Official Membership Types

The NSS ERP recognizes:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

These correspond to the official NSS Bye-Law Membership categories.

---

# 5. Probationary Membership

A Person enrolled as a Probationary Member receives the appropriate Membership identity and Anumati Patra.

The official Bye-Law states that a Probationary Member must satisfy the prescribed qualifications and is issued an Anumati Patra after enrollment.

Lifecycle:

```text
Applicant
    |
Eligibility
    |
Approval / Enrollment
    |
PROBATIONARY
    |
Anumati Patra
```

---

# 6. Probationary to Regular Progression

The standard progression is:

```text
PROBATIONARY
      |
Required Period
      |
Training
      |
Sakha Recommendation
      |
Regular Enrollment
      |
REGULAR
      |
Parichaya Patra
```

The Bye-Law specifies at least one year as a Probationary Member with a valid Anumati Patra and at least one year of training under Kendra Sangha guidance for the normal Regular Member route.

The ERP shall preserve the progression history.

---

# 7. Direct Regular Membership

The Bye-Law also provides that the Parichalak may directly enroll a devotee as a Regular Member and subsequently direct the person to become a member of a Sakha Sangha.

Therefore the ERP shall support:

```text
Applicant
    |
Parichalak Decision
    |
REGULAR
```

without forcing the normal Probationary progression when the authoritative rule permits direct Regular enrollment.

---

# 8. Associate Membership

Associate Membership is an independent official Membership category.

Lifecycle:

```text
Person
    |
Associate Membership Decision
    |
ASSOCIATE
```

The Bye-Law permits the Parichalak, suo motu or on recommendation of a Sakha Sangha, to enroll a person as an Associate Member based on active participation and sympathetic attitude toward Kendra Sangha activities.

Associate Members may attend functions of Sakha Sanghas and the Kendra Sangha but do not have the specified elected-post voting/election rights described by the Bye-Law.

---

# 9. Darshak Operational Concept

Darshak is not an official Membership Type.

The ERP database shall therefore use:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

and not:

```text
DARSHAK
```

Operationally, "Darshak" may be used in Attendance and UI contexts.

A Darshak may include:

```text
Probationary Member
```

or:

```text
Regular Member of another Sakha
```

as defined by the approved Darshak Business Rule.

The detailed rule is maintained separately in:

```text
docs/03_Solution/modules/attendance/DARSHAK_BUSINESS_RULE.md
```

---

# 10. Membership Status Lifecycle

Membership Type is separate from Membership Status.

A Membership may move through controlled status states such as:

```text
ACTIVE
    |
RENEWAL_PENDING
    |
ACTIVE
```

Other status states may include:

```text
EXPIRED
SUSPENDED
ON_HOLD
DISCIPLINARY_REVIEW
TRANSFERRED
DECEASED
```

The authoritative status master shall control the permitted values.

---

# 11. Renewal Lifecycle

Renewal preserves the Membership identity.

```text
ACTIVE
   |
Renewal Due
   |
RENEWAL_PENDING
   |
Renewal Request
   |
Approval
   |
ACTIVE
```

Renewal history is retained permanently.

The Sangha Sevi ID does not change.

---

# 12. Transfer Lifecycle

A Membership transfer does not create a new Membership identity.

```text
Current Sakha
      |
Transfer Request
      |
Verification
      |
Approval
      |
Effective Date
      |
New Sakha
```

The Sangha Sevi ID remains unchanged.

The local Sakha number may change.

Historical transfer information remains preserved.

The approved transfer workflow establishes Dola Purnima as the effective date for the transfer.

---

# 13. Membership Journey Events

Important lifecycle events shall be recorded through:

```text
membership_journey_event
```

Examples include:

```text
MEMBERSHIP_CREATED
PROBATIONARY_STARTED
TRAINING_STARTED
PROBATIONARY_REVIEW
REGULAR_ENROLMENT
ASSOCIATE_ENROLMENT
RENEWAL
TRANSFER
STATUS_CHANGE
```

The final event master shall be controlled through configuration.

---

# 14. Identity Document Lifecycle

## Anumati Patra

```text
Probationary Enrollment
        |
Anumati Patra
```

History is retained.

## Parichaya Patra

```text
Regular Enrollment
        |
Parichaya Patra
```

History is retained.

---

# 15. Attendance Review Relationship

Attendance review is separate from Membership status.

The system may identify a Membership for attendance review.

The review itself does not automatically change Membership status.

The frozen Attendance Enforcement design requires human review before Membership action.

Therefore:

```text
Attendance
    |
Attendance Review
    |
Human Decision
    |
Possible Membership Action
```

and not:

```text
Attendance
    |
Automatic Suspension
```

---

# 16. Membership History

Membership history shall never be physically deleted.

Historical information includes:

* Membership status.
* Renewal.
* Transfer.
* Probationary review.
* Membership journey events.
* Identity documents.
* Organizational history.

---

# 17. Lifecycle Summary

```text
PERSON
   |
   +-- No Membership
   |
   +-- Membership Application / Enrollment
             |
             +-- PROBATIONARY
             |       |
             |       +-- Anumati Patra
             |       |
             |       +-- Review + Training
             |                 |
             |              REGULAR
             |                 |
             |                 +-- Parichaya Patra
             |
             +-- ASSOCIATE
```

All Membership paths generate and retain the Membership identity according to the applicable enrollment rules.

---

# 18. Core Lifecycle Principles

```text
Person is not equal to Member

One Person = One Membership

One Membership = One Sangha Sevi ID

Sangha Sevi ID is Permanent

Sangha Sevi ID is Never Reused

Transfer Does Not Change Sangha Sevi ID

Renewal Does Not Change Sangha Sevi ID

Membership History Is Never Deleted

Attendance Review Does Not Automatically Change Membership Status
```

---

# End of Document
