# NSS ERP — Family Lifecycle

**Document ID:** SOL-FAM-005  
**Version:** 1.0.0  
**Status:** DRAFT  
**Module:** Family  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the Family
Module entities:

- `family_group`
- `family_relationship`
- `family_head_history`
- `family_transition_history`

The Family lifecycle is independent of Membership lifecycle.

---

# 2. Source Authority

This lifecycle document is governed by:

- Family Module Overview (SOL-FAM-001)
- Family Business Rules (SOL-FAM-003)
- Family Table Design (SOL-FAM-004)
- Person Lifecycle (SOL-PER-005)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. Family Group — Lifecycle States

```text
ACTIVE          is_active=TRUE, deleted_at=NULL
INACTIVE        is_active=FALSE, deleted_at=SET
```

---

# 4. State Definitions

## ACTIVE

The Family Group is operationally current. It may contain active family
relationships and a designated Family Head.

## INACTIVE

The Family Group has been soft-deleted or dissolved. The record remains
physically present for historical traceability. All historical
relationships and transitions remain preserved.

---

# 5. Family Group State Transition Diagram

```text
              FORMED (Creation)
                     |
                     v
                  ACTIVE
                 /       \
    Normal ops  /         \  Dissolution / Soft Delete
               v           v
           ACTIVE       INACTIVE
                           |
                      Restore (authorized)
                           |
                           v
                        ACTIVE
```

---

# 6. Transition: Formation -> ACTIVE

**Trigger:** New Family Group created

**Preconditions:**
- At least one Person associated (initial family member)
- Family ID generated via centralized sequence
- Valid sakha_pk reference (organizational association)

**Effects:**
- `family_group_pk` assigned (UUID)
- `family_id` assigned (FG000001 format)
- `is_active` = TRUE
- `created_at` = current timestamp

**Audit:** Family creation is audited (FAM-029)

---

# 7. Transition: ACTIVE -> ACTIVE (Update)

**Trigger:** Family Group attributes updated (name, status, remarks)

**Preconditions:**
- Authorized user with appropriate permission

**Effects:**
- Attribute(s) updated
- `updated_at` = current timestamp
- Identity (family_group_pk, family_id) unchanged

**Audit:** Changes are audited (FAM-029)

---

# 8. Transition: ACTIVE -> INACTIVE (Dissolution / Soft Delete)

**Trigger:** Family Group dissolved or administratively soft-deleted

**Preconditions:**
- Authorized user with appropriate permission
- Business justification exists

**Effects:**
- `is_active` = FALSE
- `deleted_at` = current timestamp

**Constraints:**
- Physical deletion is prohibited (FAM-028)
- Historical relationships are preserved (FAM-027)
- Historical transitions remain traceable (FAM-013)
- Family ID is never reused (FAM-002)

**Audit:** Dissolution is audited

---

# 9. Transition: INACTIVE -> ACTIVE (Restore)

**Trigger:** Authorized reversal of dissolution/soft-delete

**Preconditions:**
- Authorized user with administrative permission
- Business justification exists

**Effects:**
- `is_active` = TRUE
- `deleted_at` = NULL
- `updated_at` = current timestamp

---

# 10. Family Relationship — Lifecycle

## Relationship States

```text
CURRENT         is_current=TRUE, effective_to=NULL
ENDED           is_current=FALSE, effective_to=SET
```

---

# 11. Transition: Addition -> CURRENT

**Trigger:** Person added to a Family Group

**Preconditions:**
- Valid `person_pk` reference (Person must exist)
- Valid `family_group_pk` reference (Family must be ACTIVE)
- Valid `relationship_type_pk` (controlled master data — FAM-007)
- No duplicate active relationship for same Person+Family+Type

**Effects:**
- `family_relationship_pk` assigned (UUID)
- `is_current` = TRUE
- `effective_from` = effective date
- `effective_to` = NULL
- `created_at` = current timestamp

**Rules:**
- Existing Person record is reused (FAM-016)
- No duplicate Person created (FAM-005)

---

# 12. Transition: CURRENT -> ENDED

**Trigger:** Relationship ends (death, family transition, correction)

**Preconditions:**
- Authorized user
- Business justification

**Effects:**
- `is_current` = FALSE
- `effective_to` = end date
- `updated_at` = current timestamp

**Constraints:**
- Record remains physically present (FAM-028)
- Historical relationship preserved (FAM-008)

---

# 13. Family Head — Lifecycle

Family Head changes are recorded as historical events in
`family_head_history`. Each record is append-only.

## Transition: New Head Assignment

**Trigger:** Family Head designated or changed

**Preconditions:**
- Person must be a current member of the Family Group
- Family Group must be ACTIVE
- Authorized user

**Effects:**
- Previous head record: `effective_to` = transition date
- New record created:
  - `family_head_history_pk` assigned (UUID)
  - `person_pk` = new head
  - `effective_from` = assignment date
  - `effective_to` = NULL
  - `created_at` = current timestamp

**Constraints:**
- Historical head assignments are never deleted (FAM-010)
- Both old and new assignments remain traceable

---

# 14. Family Transition — Lifecycle

Family transitions are recorded as historical events in
`family_transition_history`. Each record is append-only.

## Transition Types

```text
MARRIAGE            Person moves to new/spouse Family
NEW_FAMILY          Person forms a new Family Group
FAMILY_CHANGE       Person moves between existing Families
OTHER               Other approved transitions
```

---

# 15. Transition: Marriage

**Trigger:** Marriage results in Family Group change (FAM-014)

**Process:**
```text
Person in Old Family (FG0001)
       |
Marriage
       |
New Family formed or joined (FG0100)
       |
Transition record created
       |
Old relationship ended (is_current=FALSE)
       |
New relationship created in new Family
```

**Effects on family_transition_history:**
- `person_pk` = transitioning Person
- `old_family_group_pk` = source Family
- `new_family_group_pk` = target Family
- `transition_type` = MARRIAGE
- `effective_date` = marriage/transition date
- `created_at` = current timestamp

**Constraints:**
- Old Family Group remains preserved (FAM-013)
- Historical link maintained (FAM-015)
- Person identity unchanged (FAM-016)
- No duplicate Person created

---

# 16. Transition: New Family Formation

**Trigger:** Person(s) form a new Family Group

**Process:**
```text
Person(s) in existing Family
       |
Decision to form new Family
       |
New Family Group created (ACTIVE)
       |
Transition record(s) created
       |
Old relationship(s) ended
       |
New relationship(s) created in new Family
```

---

# 17. Cross-Module Lifecycle Events

The Family Module responds to and generates the following lifecycle events:

## Events Family Responds To

| Source Event | Source Module | Family Response |
|---|---|---|
| Person Death Recorded | Person | End current relationships for deceased; preserve history |
| Person Soft-Deleted | Person | Relationships remain as historical references |
| Person Merged | Person | FK references transferred to target Person |

## Events Family Generates

| Family Event | Affected Modules | Expected Response |
|---|---|---|
| Family Dissolved | Membership (display), Youth (display) | Dashboard views update |
| Person Transitions Family | Membership (no change), Youth (context update) | Organizational views may update |

---

# 18. Person Death and Family

When a Person's death is recorded (Person Module event):

- Family relationships for the deceased Person:
  - `is_current` = FALSE
  - `effective_to` = date of death (or recording date)
- Family Head (if deceased was head):
  - Current head record: `effective_to` = date
  - New head must be designated separately
- Family Group itself: remains ACTIVE (other members continue)
- Historical records: fully preserved

The Family Module does not independently record death — it responds to
the Person lifecycle event.

---

# 19. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of Family Group records (FAM-028)
- Physical deletion of historical relationships (FAM-028)
- Physical deletion of transition history (FAM-028)
- Physical deletion of head history (FAM-010)
- Creating duplicate Person on family change (FAM-016)
- Reusing a dissolved Family ID (FAM-002)
- Destroying old Family on marriage transition (FAM-013)
- Family Module creating Membership identity (FAM-019)
```

---

# 20. Lifecycle and Audit Integration

| Transition | Audit Fields |
|---|---|
| Family Formation | created_at, created_by |
| Family Update | updated_at, updated_by |
| Family Dissolution | deleted_at (soft-delete timestamp) |
| Relationship Addition | created_at |
| Relationship End | updated_at |
| Head Change | created_at (new record) |
| Family Transition | created_at, created_by |

---

# 21. Lifecycle State Query Patterns

| Query Intent | Filter |
|---|---|
| Active families | `family_group.is_active = TRUE` |
| Current family members | `family_relationship.is_current = TRUE` |
| Current family head | `family_head_history.effective_to IS NULL` |
| Historical relationships | `family_relationship.is_current = FALSE` |
| All transitions for a person | `family_transition_history.person_pk = ?` |

---

# 22. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact Family dissolution workflow and authorization
Exact marriage transition UI/workflow
Exact Person-death event consumption mechanism
Exact Family Group naming conventions
Exact transition_type vocabulary beyond examples
Exact notification to downstream modules
```

---

# 23. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
1.0.0
```
