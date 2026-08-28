# NSS ERP — Membership Business Rules

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Membership Business Rules |
| Document ID | SOL-MEM-004 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/04_membership_business_rules.md |
| Version | 1.0.0 |
| Status | Draft |
| Authority | NSS ERP Membership Module |
| Parent Document | 01_membership_module_overview.md |
| Related Documents | 02_membership_erd.md, 03_membership_lifecycle.md, 05_membership_table_design.md |
| Effective Date | TBD |

---

# 1. Purpose

This document defines the business rules governing the NSS ERP Membership Module.

These rules translate approved NSS Membership principles and authoritative Bye-Law provisions into ERP implementation requirements.

Where an authoritative NSS Bye-Law conflicts with an ERP rule, the authoritative Bye-Law shall prevail.

---

# 2. Membership Identity Rules

## MBR-001 — Person Is Not Membership

A Person record shall not automatically create a Membership.

```text
Person is not equal to Member
```

A Person may exist without Membership.

---

## MBR-002 — Membership Requires Person

Every Membership shall belong to exactly one Person.

A Membership shall not exist without a Person.

---

## MBR-003 — One Person One Membership

A Person may have only one active Membership identity.

```text
One Person
    |
One Membership
```

---

## MBR-004 — Sangha Sevi ID

Every Membership shall have one Sangha Sevi ID.

The Sangha Sevi ID shall be:

* System generated.
* Globally unique.
* Permanent.
* Never reused.
* Never changed.

---

## MBR-005 — Membership Identity Preservation

Membership identity shall remain unchanged throughout Membership lifecycle events unless an authoritative rule explicitly requires otherwise.

---

# 3. Membership Type Rules

## MBR-006 — Official Membership Types

The Membership Type master shall support:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

These correspond to the official NSS Bye-Law categories.

---

## MBR-007 — Darshak Is Not Membership Type

DARSHAK shall not be stored as a Membership Type.

The operational Darshak concept is defined separately by:

```text
DARSHAK_BUSINESS_RULE.md
```

---

## MBR-008 — Full Member Terminology

FULL_MEMBER shall not be used as the authoritative database Membership Type.

The official ERP value is:

```text
REGULAR
```

---

# 4. Probationary Membership Rules

## MBR-009 — Probationary Enrollment

A Person may be enrolled as a Probationary Member after satisfying the applicable authoritative qualifications and enrollment process.

---

## MBR-010 — Anumati Patra

A Probationary Member shall be associated with an Anumati Patra according to the applicable NSS process.

The Bye-Law states that an enrolled Probationary Member is issued an Anumati Patra.

---

## MBR-011 — Probationary Duration

The normal progression to Regular Membership requires the prescribed Probationary period.

The Bye-Law specifies at least one year as a Probationary Member holding a valid Anumati Patra.

---

# 5. Regular Membership Rules

## MBR-012 — Regular Membership

Regular Membership is the full-fledged Membership category defined by the NSS Bye-Law.

---

## MBR-013 — Normal Regular Progression

The normal progression is:

```text
Probationary
    |
Required Period
    |
Training
    |
Sakha Recommendation
    |
Regular
```

The Bye-Law specifies at least one year of Probationary Membership and at least one year of training under Kendra Sangha guidance for the normal route.

---

## MBR-014 — Parichaya Patra

A Regular Member shall be associated with a Parichaya Patra according to the applicable NSS process.

---

## MBR-015 — Direct Regular Enrollment

The ERP shall support direct Regular enrollment where authorized by the Parichalak under the Bye-Law.

The direct-enrollment path shall be recorded as a Membership journey event.

---

# 6. Associate Membership Rules

## MBR-016 — Associate Membership

Associate Membership is an independent official Membership category.

---

## MBR-017 — Associate Enrollment Authority

Associate Membership may be enrolled by the Parichalak suo motu or on recommendation of a Sakha Sangha, subject to the applicable NSS rules.

---

## MBR-018 — Associate Participation

Associate Members may attend functions of Sakha Sanghas and the Kendra Sangha according to the Bye-Law.

---

## MBR-019 — Associate Governance Restrictions

Associate Members shall not be granted governance rights beyond those permitted by the authoritative NSS rules.

The ERP shall derive governance eligibility from the Governance Module rather than assuming that Membership alone grants governance authority.

---

# 7. Membership Status Rules

## MBR-020 — Type and Status Separation

Membership Type and Membership Status shall be maintained independently.

Example:

```text
Membership Type:
REGULAR

Membership Status:
ACTIVE
```

---

## MBR-021 — Status History

Every Membership status transition shall be recorded historically.

---

## MBR-022 — No Physical Deletion

Membership records and historical status records shall not be physically deleted.

---

# 8. Renewal Rules

## MBR-023 — Renewal Identity

Membership renewal shall not create a new Sangha Sevi ID.

---

## MBR-024 — Renewal History

Every approved renewal shall be preserved in Membership renewal history.

---

## MBR-025 — Renewal Request

A renewal request shall be separately identifiable from the final renewal history.

---

## MBR-026 — Renewal Status

The ERP shall support a controlled renewal workflow.

The exact renewal dates and deadline rules shall follow the approved NSS Membership Renewal rules and applicable authoritative references.

---

# 9. Transfer Rules

## MBR-027 — Transfer Identity

Membership transfer shall not change the Sangha Sevi ID.

---

## MBR-028 — Transfer History

Every Membership transfer shall be recorded in:

```text
membership_transfer_history
```

---

## MBR-029 — Transfer Effective Date

The approved Membership Transfer workflow establishes Dola Purnima as the effective date of transfer.

---

## MBR-030 — Local Sakha Number

A Member may receive a new local Sakha number following transfer.

The local number is not the global Membership identity.

---

## MBR-031 — Transfer History Preservation

Previous Sakha association shall remain historically traceable.

---

# 10. Probationary Review Rules

## MBR-032 — Review History

Probationary Member reviews shall be historically preserved.

---

## MBR-033 — Review Does Not Delete Membership

A review shall not delete the underlying Membership record.

---

## MBR-034 — Review Outcome

Review outcomes shall be recorded as controlled journey/review events.

The exact review outcomes shall follow the approved Membership progression rules.

---

# 11. Attendance Relationship

## MBR-035 — Attendance Is Separate

Attendance belongs to the Attendance Module.

Membership stores the Membership identity and lifecycle.

---

## MBR-036 — Attendance Review

Attendance may result in an Attendance Review.

Attendance Review is not itself a Membership status.

---

## MBR-037 — No Automatic Membership Action

Attendance alone shall not automatically:

* Suspend Membership.
* Cancel Membership.
* Change Membership Type.
* Revoke identity documents.

A formal review and authorized decision are required before Membership action.

---

# 12. Organization Relationship

## MBR-038 — Current Organization

The Membership record shall identify the Member's current organizational association.

---

## MBR-039 — Historical Organization

Previous organizational associations shall remain available through transfer history.

---

# 13. Governance Eligibility

## MBR-040 — Membership Is Not Governance Authority

Membership does not automatically grant a governance position.

Governance eligibility shall be determined by Governance rules.

---

## MBR-041 — Governance Traceability

Where Membership eligibility affects a governance workflow, the relationship shall remain traceable.

---

# 14. Audit Rules

## MBR-042 — Auditability

Membership actions shall preserve:

```text
Created By
Created At
Updated By
Updated At
```

where applicable.

---

## MBR-043 — Historical Traceability

Membership history shall remain traceable throughout the lifecycle.

---

# 15. Deletion Rules

## MBR-044 — Physical Deletion Prohibited

Physical deletion of Membership history is prohibited.

---

## MBR-045 — Status-Based Lifecycle

When Membership ceases or becomes inactive, the ERP shall record the appropriate status/event rather than physically deleting the Membership record.

---

# 16. Core Frozen Rules

The following principles are frozen at the project level:

```text
Person is not equal to Member

One Person = One Membership

One Membership = One Sangha Sevi ID

Sangha Sevi ID Permanent

Sangha Sevi ID Never Reused

Transfer Does Not Change Sangha Sevi ID

Membership History Never Deleted

Physical Delete Prohibited

Attendance Review Required Before Membership Action
```

---

# 17. Authority Hierarchy

Membership rules shall be interpreted according to:

```text
NSS Bye-Law
      |
Authoritative REF
      |
Approved Governance Decision
      |
Approved Membership Business Rule
      |
Solution Design
      |
Implementation
```

Where a conflict exists, the higher authority shall prevail.

---

# End of Document
