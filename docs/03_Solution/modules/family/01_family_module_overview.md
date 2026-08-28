# NSS ERP Family Module Overview

Version: 1.0

Status: DRAFT

---

# 1. Purpose

The Family Module manages NSS family identity, family membership, family relationships, family head history, family transitions, and family-level visibility within the NSS ERP.

The Family Module is built on top of the Person Module.

The Family Module supports the NSS Family First model.

---

# 2. Core Principle

Family is independent of Membership.

```text
Person is not equal to Member
Family is not equal to Membership
```

A Person may exist without Membership.

A Person may belong to a Family without being an NSS Member.

A Family may contain both Members and non-Members.

---

# 3. Family First Model

The NSS ERP shall treat the family as an important organizational and information unit.

The Family Module provides a unified view of:

* Family Members
* Non-member Family Persons
* Family Relationships
* Membership status
* Youth participation
* Family activities
* Family history

---

# 4. Family Identity

Each NSS Family shall have a unique Family ID.

Example:

```text
FG000001
FG000002
FG000003
```

Rules:

* System Generated
* Globally Unique
* Permanent
* Never Reused
* Never Changed

---

# 5. Family Group

The core Family entity is:

```text
family_group
```

A Family Group represents an NSS family unit.

A Family Group may contain:

* Father
* Mother
* Husband
* Wife
* Son
* Daughter
* Children
* Other approved family relationships

---

# 6. Person Relationship

Family members are Persons.

Relationship:

```text
Person
    |
Family Relationship
    |
Family Group
```

The Family Module shall reference the Person Module rather than duplicating Person identity information.

---

# 7. Membership Relationship

A Family may contain:

```text
Regular Members
Probationary Members
Associate Members
Non-Members
```

Membership is maintained by the Membership Module.

Family only provides the relationship between the Person and the Family.

---

# 8. Family Head

A Family may have a designated Family Head.

Family Head information shall be maintained separately from the Family Group record.

Historical Family Head assignments shall be preserved.

The historical entity is:

```text
family_head_history
```

---

# 9. Family Relationships

Family relationships are maintained through:

```text
family_relationship
```

Examples include:

```text
FATHER
MOTHER
HUSBAND
WIFE
SON
DAUGHTER
```

Additional relationship types shall be controlled through master data where required.

---

# 10. Family Transition

Family structure may change during the lifecycle of a Person.

Examples include:

* Marriage
* Formation of a new family
* Change of family unit
* Other approved family transitions

Family transition history shall be preserved through:

```text
family_transition_history
```

---

# 11. Marriage and Family Transition

Marriage may result in a change of Family Group.

The ERP shall preserve:

```text
Previous Family
        |
Marriage / Family Transition
        |
New Family
```

Historical links shall not be destroyed.

---

# 12. Person Without Membership

The Family Module shall support Persons who do not have NSS Membership.

Examples:

* Spouse of a Member
* Child
* Guardian
* Kumari Participant
* Kishor Participant
* Future Applicant
* Historical Person

Therefore:

```text
Person is not equal to Membership
```

---

# 13. Youth Program Visibility

Family members may have participation in NSS youth programs.

The Family Module shall support visibility of:

```text
Kumari Sangha

Kishor Puja

Future Youth Programs
```

Family visibility shall be restricted to the user's authorized family scope.

---

# 14. Family Visibility Information

Where authorized, family users may view:

* Participant Details
* Registration Details
* Activity History
* Training History
* Participation Status
* Assigned Guardian
* Membership Transition Status

The frozen family visibility rule restricts access to the user's own family records.

---

# 15. Family Dashboard

The Family Dashboard provides a consolidated view of the Family.

It may display:

```text
Family ID
Family Name
Sakha
Family Status
```

and:

```text
Family Members
Membership Summary
Kumari Participation
Kishor Participation
Family Activities
Family Tree
Transition History
```

---

# 16. Relationship With Membership Module

Membership remains the authoritative source for:

* Sangha Sevi ID
* Membership Type
* Membership Status
* Membership Lifecycle
* Renewal
* Transfer

Family remains the authoritative source for:

* Family identity
* Family relationships
* Family grouping
* Family head history
* Family transitions

---

# 17. Relationship With Kumari Module

Kumari participation is maintained by the Kumari Module.

The Family Module provides family context.

A Kumari Participant does not automatically become an NSS Member.

---

# 18. Relationship With Kishor Module

Kishor participation is maintained by the Kishor Module.

The Family Module provides family context.

Guardian assignment is maintained by the Kishor Module.

---

# 19. Relationship With Mahila Module

Mahila Sangha participation is maintained by the Mahila Module.

Family provides the family relationship and family context.

---

# 20. Audit Principles

Family actions shall preserve:

* Created By
* Updated By
* Timestamp
* Historical Traceability

Family history shall not be physically deleted.

---

# 21. Deletion Principles

Physical deletion of historical Family information is prohibited.

Family relationships and transitions shall be preserved historically.

---

# 22. Frozen Decisions

* Family First Model
* Person is not equal to Member
* Family may contain Members and non-Members
* Family ID is permanent
* Family ID is never reused
* Family relationships are maintained separately
* Family Head history is preserved
* Family transition history is preserved
* Marriage-related family transitions are preserved
* Youth participation can be viewed through authorized Family access
* Family history is never physically deleted

---

# 23. Module Dependencies

```text
Foundation
    |
Person
    |
Family
    +-- Membership
    +-- Kumari
    +-- Kishor
    +-- Mahila
    +-- Governance / Activities
```

---

# 24. Summary

The Family Module provides the authoritative NSS Family identity and relationship management system.

It is the authoritative source for:

* Family ID
* Family Group
* Family Relationships
* Family Head History
* Family Transition History
* Family-level visibility

---

# End of Document
