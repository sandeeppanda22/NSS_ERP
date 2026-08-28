# NSS ERP Family Table Design

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Family Table Design |
| Document ID | SOL-FAM-004 |
| Domain | Family |
| Repository Path | docs/03_Solution/modules/family/04_family_table_design.md |
| Version | 1.0.0 |
| Status | DRAFT |
| Parent Document | 01_family_module_overview.md |

---

# 1. Purpose

This document defines the logical PostgreSQL table design for the NSS ERP Family Module.

The frozen Family table set contains:

```text
family_group

family_head_history

family_relationship

family_transition_history
```

---

# 2. Family Table Set

```text
family_group
family_head_history
family_relationship
family_transition_history
```

The fourth table, family_transition_history, was added as part of the frozen Marriage and Family Transition decision.

---

# 3. family_group

## Purpose

Stores the core Family identity.

---

## Main Columns

```text
family_group_pk

family_id

family_name

family_status

sakha_pk

formed_date

remarks

created_at

updated_at

deleted_at

is_active
```

---

## Key Rules

```text
family_group_pk
    PRIMARY KEY

family_id
    UNIQUE NOT NULL
```

---

# 4. Family ID

The business identifier is:

```text
family_id
```

Example:

```text
FG000001
FG000002
FG000003
```

Rules:

```text
System Generated
Globally Unique
Permanent
Never Reused
Never Changed
```

---

# 5. family_relationship

## Purpose

Connects a Person to a Family Group.

---

## Main Columns

```text
family_relationship_pk

family_group_pk

person_pk

relationship_type_pk

effective_from

effective_to

is_current

remarks

created_at

updated_at
```

---

# 6. family_relationship Constraints

The relationship shall reference:

```text
family_group_pk
person_pk
relationship_type_pk
```

Foreign keys:

```text
family_group_pk
    to family_group.family_group_pk

person_pk
    to person.person_pk
```

Relationship type shall be controlled through the project master-data system.

---

# 7. Family Relationship Examples

```text
FATHER
MOTHER
HUSBAND
WIFE
SON
DAUGHTER
```

The actual master-data catalogue may contain additional approved relationships.

---

# 8. family_head_history

## Purpose

Stores historical Family Head assignments.

---

## Main Columns

```text
family_head_history_pk

family_group_pk

person_pk

effective_from

effective_to

reason

remarks

created_at
```

---

# 9. Family Head History

Example:

```text
Family FG000001

2020
    |
Person A = Family Head

2025
    |
Person B = Family Head
```

Both assignments remain historically traceable.

---

# 10. family_transition_history

## Purpose

Stores historical transitions between Family Groups.

---

## Main Columns

```text
family_transition_history_pk

person_pk

old_family_group_pk

new_family_group_pk

transition_type

transition_reason

effective_date

remarks

created_at

created_by
```

---

# 11. Family Transition Example

Example:

```text
Old Family
FG0001
    |
Marriage
    |
New Family
FG0100
```

The transition record preserves:

```text
Person
Old Family
New Family
Reason
Effective Date
```

This model was established to preserve NSS Family lineage during marriage-related transitions.

---

# 12. Marriage Transition

A marriage transition may result in:

```text
Existing Person
    |
Marriage
    |
New Family Group
```

The original Family Group remains preserved.

---

# 13. Person Foreign Key

Family relationships shall reference:

```text
person.person_pk
```

The Family Module shall not duplicate Person identity fields.

---

# 14. Membership Relationship

Membership is referenced indirectly through Person.

Relationship:

```text
family_relationship
        |
person
        |
sangha_sevi
```

The Family Module shall not create a separate Membership identity.

---

# 15. Youth Program Relationship

Family dashboards may obtain youth information through:

```text
person
family_group
```

and then retrieve authoritative participation information from:

```text
kumari_membership

kumari_activity_participant

kishor_participant

kishor_event_participation
```

The frozen Family Visibility design identifies these relationships as part of the Family view layer.

---

# 16. Optional Family Visibility View

The project identified the possibility of a unified view:

```text
vw_family_youth_participation
```

This view may combine:

```text
person
family_group

kumari_membership
kumari_activity_participant

kishor_participant
kishor_event_participation
```

The view is an implementation option for Family Dashboard / Parent Portal / Youth Reports and is not a replacement for the underlying authoritative tables.

---

# 17. Primary Key Standard

Family transactional tables shall use internal UUID primary keys.

Examples:

```text
family_group_pk

family_relationship_pk

family_head_history_pk

family_transition_history_pk
```

---

# 18. Foreign Key Standard

Foreign keys shall reference internal primary keys.

Examples:

```text
person_pk

family_group_pk

relationship_type_pk
```

Business identifiers such as:

```text
family_id
person_id
```

shall not replace internal primary-key relationships.

---

# 19. Audit Columns

Applicable Family tables shall preserve:

```text
created_at

created_by

updated_at

updated_by
```

Historical records shall retain sufficient audit information for traceability.

---

# 20. Soft Delete

Physical deletion of historical Family information is prohibited.

Family records shall be managed through controlled lifecycle/status mechanisms.

---

# 21. Historical Integrity

The following information shall remain preserved:

```text
Family Identity

Family Relationships

Family Head History

Family Transitions

Marriage-related Family Transitions
```

---

# 22. Data Ownership

| Data                  | Owner             |
| --------------------- | ----------------- |
| Person Identity       | Person Module     |
| Membership            | Membership Module |
| Family Identity       | Family Module     |
| Family Relationship   | Family Module     |
| Family Head           | Family Module     |
| Family Transition     | Family Module     |
| Kumari Participation  | Kumari Module     |
| Kishor Participation | Kishor Module    |
| Guardian Assignment   | Kishor Module    |
| Mahila Participation  | Mahila Module     |

---

# 23. Final Family Table Set

```text
family_group

family_head_history

family_relationship

family_transition_history
```

---

# 24. Family Database Principles

```text
Family First

Person is not equal to Member

Family is not equal to Membership

One Person May Exist Without Membership

Family May Contain Members and Non-Members

Family History Never Deleted

Family Transition History Preserved

No Duplicate Person Records

Module Data Ownership Preserved

Auditability
```

---

# End of Document
