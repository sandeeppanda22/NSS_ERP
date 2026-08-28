# NSS ERP Family Business Rules

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Family Business Rules |
| Document ID | SOL-FAM-003 |
| Domain | Family |
| Repository Path | docs/03_Solution/modules/family/03_family_business_rules.md |
| Version | 1.0.0 |
| Status | DRAFT |
| Parent Document | 01_family_module_overview.md |

---

# 1. Purpose

This document defines the business rules governing the NSS ERP Family Module.

---

# 2. Family Identity Rules

## FAM-001 — Family Identity

Every registered NSS Family shall have a unique Family ID.

---

## FAM-002 — Family ID Permanence

Family ID shall be:

* System generated.
* Globally unique.
* Permanent.
* Never reused.
* Never changed.

---

# 3. Person and Family Rules

## FAM-003 — Person Independent of Membership

A Person may exist without Membership.

```text
Person is not equal to Member
```

---

## FAM-004 — Family May Contain Non-Members

A Family may contain Persons who are not NSS Members.

Examples:

* Spouse
* Child
* Guardian
* Kumari Participant
* Kishor Participant
* Future Applicant
* Historical Person

---

## FAM-005 — Person Data Ownership

Person identity information shall remain owned by the Person Module.

The Family Module shall reference Person records.

---

# 4. Family Relationship Rules

## FAM-006 — Relationship Ownership

Family relationships shall be maintained by the Family Module.

---

## FAM-007 — Controlled Relationship Types

Family relationship types shall be maintained through controlled master data where applicable.

Examples:

```text
FATHER
MOTHER
HUSBAND
WIFE
SON
DAUGHTER
```

---

## FAM-008 — Relationship History

Changes to important Family relationships shall preserve historical information where required.

---

# 5. Family Head Rules

## FAM-009 — Family Head

A Family may have a designated Family Head.

---

## FAM-010 — Family Head History

Changes to Family Head shall be historically recorded.

Historical Family Head assignments shall not be deleted.

---

# 6. Family Transition Rules

## FAM-011 — Family Transition

The ERP shall support Family transitions.

Examples:

* Marriage
* New Family Formation
* Change of Family Unit
* Other approved transitions

---

## FAM-012 — Transition History

Family transitions shall be stored in:

```text
family_transition_history
```

---

## FAM-013 — Historical Family Preservation

A previous Family shall remain historically traceable after a transition.

The system shall not destroy the old Family record merely because a Person joins a new Family.

---

# 7. Marriage Rules

## FAM-014 — Marriage Transition

Marriage may result in the formation of a new Family Group.

Example:

```text
Original Family
    |
Marriage
    |
New Family
```

---

## FAM-015 — Historical Link

The new Family shall maintain a historical relationship with the previous Family where applicable.

---

## FAM-016 — Person Reuse

The ERP shall not create a duplicate Person record merely because the Person changes Family.

The existing Person record shall continue to be used.

---

# 8. Membership Relationship Rules

## FAM-017 — Membership Ownership

Membership information shall remain owned by the Membership Module.

---

## FAM-018 — Family Membership View

The Family Module may display Membership information for family members.

Displayed information may include:

```text
Sangha Sevi ID
Membership Type
Membership Status
```

---

## FAM-019 — No Duplicate Membership

Family shall not create a separate Family Membership ID.

The authoritative Membership identity remains the Sangha Sevi ID.

---

# 9. Youth Program Rules

## FAM-020 — Kumari Visibility

Authorized Family users may view relevant Kumari participation information for members of their own Family.

---

## FAM-021 — Kishor Visibility

Authorized Family users may view relevant Kishor participation information for members of their own Family.

---

## FAM-022 — Future Youth Programs

The Family visibility model shall be extensible to future youth programs.

---

## FAM-023 — Family Access Scope

Family users shall only access authorized records belonging to their own Family.

The project explicitly froze this restriction.

---

# 10. Family Visibility Rules

## FAM-024 — Participation Information

Where authorized, Family users may view:

* Participant Details
* Registration Details
* Activity History
* Training History
* Participation Status
* Assigned Guardian
* Membership Transition Status

---

## FAM-025 — Data Ownership

Family visibility shall aggregate information from the authoritative module.

The Family Module shall not duplicate the complete source records of:

* Membership
* Kumari
* Kishor
* Mahila
* Attendance

---

# 11. Family Dashboard Rules

## FAM-026 — Family Dashboard

The Family Dashboard shall provide:

```text
Family Information

Family Members

Membership Summary

Kumari Participation

Kishor Participation

Family Activities

Family Tree

Family Transition History
```

---

# 12. Family History Rules

## FAM-027 — History Preservation

Family history shall be preserved.

---

## FAM-028 — No Physical Deletion

Physical deletion of historical Family relationships or transitions is prohibited.

---

# 13. Audit Rules

## FAM-029 — Auditability

Family actions shall preserve applicable:

```text
Created By
Created At
Updated By
Updated At
```

---

## FAM-030 — Historical Traceability

Family changes shall remain traceable throughout the lifecycle.

---

# 14. Module Boundary Rules

## FAM-031 — Person Boundary

Person identity belongs to Person Module.

---

## FAM-032 — Membership Boundary

Membership identity belongs to Membership Module.

---

## FAM-033 — Kumari Boundary

Kumari participation belongs to Kumari Module.

---

## FAM-034 — Kishor Boundary

Kishor participation and guardian assignment belong to Kishor Module.

---

## FAM-035 — Mahila Boundary

Mahila participation belongs to Mahila Module.

---

# 15. Frozen Family Principles

```text
Family First Model

Person is not equal to Member

Family is not equal to Membership

Family May Contain Members and Non-Members

Family ID Permanent

Family ID Never Reused

Family Head History Preserved

Family Transition History Preserved

Marriage Transition Preserved

No Duplicate Person Records

Youth Visibility Restricted to Authorized Family

Family History Never Physically Deleted
```

---

# 16. Authority Hierarchy

Family implementation shall follow:

```text
NSS Bye-Law / Authoritative References
        |
Approved Governance Decisions
        |
Approved Family Business Rules
        |
Solution Design
        |
Implementation
```

Where an authoritative source does not define an implementation detail, the project decision shall be explicitly treated as an ERP implementation decision.

---

# End of Document
