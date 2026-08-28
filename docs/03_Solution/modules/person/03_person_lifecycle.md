# NSS ERP — Person Lifecycle

**Document ID:** SOL-PER-005  
**Version:** 1.0.0  
**Status:** DRAFT  
**Module:** Person  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the Person
Module entities:

- `person`
- `document_master`

The Person lifecycle is independent of:

- Membership lifecycle
- Organization lifecycle
- Governance lifecycle
- Attendance lifecycle

A Person may remain in the system regardless of downstream domain changes.

---

# 2. Source Authority

This lifecycle document is governed by:

- Person Module Design (SOL-PER-001)
- Person Business Rules (SOL-PER-003)
- Person Table Design (SOL-PER-004)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. Person Record — Lifecycle States

The `person` table supports three operational states:

```text
ACTIVE              is_active=TRUE, date_of_death=NULL, deleted_at=NULL
ACTIVE-DECEASED     is_active=TRUE, date_of_death=SET, deleted_at=NULL
INACTIVE            is_active=FALSE, deleted_at=SET
```

---

# 4. State Definitions

## ACTIVE

The Person record is operationally current. The individual is alive (or
death has not been recorded) and the record is available for all domain
operations.

## ACTIVE-DECEASED

The individual's death has been recorded (`date_of_death` set). The Person
record remains active for historical reference, reporting, and downstream
module processing.

Death does not delete the Person (PER-BR-026).

## INACTIVE

The Person record has been soft-deleted. The record is excluded from normal
operational queries but remains physically present for historical
traceability.

---

# 5. Person State Transition Diagram

```text
                    REGISTERED (Creation)
                           |
                           v
                       ACTIVE
                      /       \
           Death Recorded      Soft Delete
                    /               \
                   v                 v
          ACTIVE-DECEASED        INACTIVE
                    \               |
              Soft Delete      Restore (authorized)
                      \           |
                       v          v
                    INACTIVE -> returns to prior state
```

---

# 6. Transition: Registration -> ACTIVE

**Trigger:** Person record creation

**Preconditions:**
- At least one contact method (mobile or email) is present (PER-BR-028)
- No duplicate Person identity detected (PER-BR-034)
- Person ID generated via centralized sequence (PER-BR-010)

**Effects:**
- `person_pk` assigned (UUID)
- `person_id` assigned (P00000001 format)
- `is_active` = TRUE
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = authorized user

**Audit:** Person creation is audited (PER-BR-074)

---

# 7. Transition: ACTIVE -> ACTIVE (Update)

**Trigger:** Authorized demographic or contact correction

**Preconditions:**
- User has appropriate RBAC permission
- Change does not violate contact requirement (PER-BR-028)
- Mobile uniqueness maintained if mobile changes (PER-BR-030)

**Effects:**
- Attribute(s) updated
- `updated_at` = current timestamp
- `updated_by_sangha_sevi_pk` = authorized user
- Identity (person_pk, person_id) unchanged (PER-BR-013/014/015)

**Audit:** Material changes are audited (PER-BR-075)

---

# 8. Transition: ACTIVE -> ACTIVE-DECEASED

**Trigger:** Death of the individual is recorded

**Preconditions:**
- Authorized user with appropriate permission
- Person is currently ACTIVE

**Effects:**
- `date_of_death` = recorded date
- `is_active` remains TRUE (death does not delete — PER-BR-026)
- `updated_at` = current timestamp
- `updated_by_sangha_sevi_pk` = authorized user

**Downstream effects (owned by respective modules — PER-BR-027):**
- Membership module may terminate membership
- Governance module may vacate positions
- Authentication module may deactivate account
- Finance module may close pending obligations

The Person Module does not independently rewrite downstream records.

**Audit:** Death recording is audited (PER-BR-075)

---

# 9. Transition: ACTIVE -> INACTIVE (Soft Delete)

**Trigger:** Authorized administrative soft-delete

**Preconditions:**
- Authorized user with appropriate permission
- Business justification exists (this is not the normal lifecycle path)

**Effects:**
- `is_active` = FALSE
- `deleted_at` = current timestamp
- `deleted_by_sangha_sevi_pk` = authorized user

**Constraints:**
- Physical deletion is prohibited for historical identity (PER-BR-071)
- Historical relationships are preserved (PER-BR-073)
- Record remains physically present in database

**Audit:** Soft-delete is audited

---

# 10. Transition: ACTIVE-DECEASED -> INACTIVE (Soft Delete)

**Trigger:** Administrative decision to soft-delete a deceased Person record

**Preconditions:**
- Same as ACTIVE -> INACTIVE
- This is a rare/exceptional operation

**Effects:**
- `is_active` = FALSE
- `deleted_at` = current timestamp
- `deleted_by_sangha_sevi_pk` = authorized user

**Constraints:**
- Same as Section 9 — historical preservation applies

---

# 11. Transition: INACTIVE -> ACTIVE (Restore)

**Trigger:** Authorized reversal of soft-delete

**Preconditions:**
- Authorized user with administrative permission
- Business justification exists

**Effects:**
- `is_active` = TRUE
- `deleted_at` = NULL
- `deleted_by_sangha_sevi_pk` = NULL
- `updated_at` = current timestamp
- `updated_by_sangha_sevi_pk` = authorized user

**Note:** Restored state depends on `date_of_death`:
- If `date_of_death` is NULL -> restores to ACTIVE
- If `date_of_death` is set -> restores to ACTIVE-DECEASED

---

# 12. Person Merge Lifecycle

**Trigger:** Authorized identity resolution for duplicate Person records

**Preconditions:**
- Duplicates identified through detection (PER-BR-034/035)
- Authorized identity-management process (PER-BR-037)
- No automatic merge (PER-BR-036)

**Process:**
```text
Duplicate Detected
       |
Manual Review
       |
Merge Authorized
       |
Target Person retains identity (person_pk, person_id)
       |
Source Person relationships transferred to Target
       |
Source Person soft-deleted (INACTIVE)
       |
Audit trail preserves full merge history
```

**Effects:**
- All downstream relationships (membership, family, governance,
  attendance, documents) transferred to target Person
- Source Person soft-deleted
- Historical traceability preserved (PER-BR-039)

**Audit:** Merge is fully audited (PER-BR-076)

---

# 13. Person Identity Corrections

**Trigger:** Authorized correction of incorrect data

**Lifecycle impact:** None — corrections do not change Person state

**Rules:**
- Name correction does not create new Person (PER-BR-013)
- Address correction does not create new Person (PER-BR-014)
- Contact correction does not create new Person (PER-BR-015)
- Corrections are audited (PER-BR-086)

---

# 14. Person Registration Sources

A Person may enter the system through multiple paths:

```text
Direct Registration -> ACTIVE
Membership Application -> Person Created -> ACTIVE -> Membership Process (separate module)
Family Addition -> Person Created -> ACTIVE -> Family Relationship (separate module)
Youth/Participant -> Person Created -> ACTIVE -> Domain Participation (Kumari/Kishor/Sevak)
```

All paths result in the same ACTIVE Person state. No path creates a
duplicate Person if the individual already exists (PER-BR-090/091/092).

---

# 15. Document Lifecycle

The `document_master` table has a simpler lifecycle:

## Document States

```text
ACTIVE          is_active=TRUE
INACTIVE        is_active=FALSE
```

## Document Transitions

```text
UPLOAD -> ACTIVE -> Supersede/Deactivate -> INACTIVE
```

---

# 16. Transition: Document Upload -> ACTIVE

**Trigger:** Document associated with a Person

**Preconditions:**
- Valid Person reference (`person_pk`)
- Valid document type (`document_type_pk`)
- Valid storage path
- Authorized user

**Effects:**
- `document_pk` assigned (UUID)
- `is_active` = TRUE
- `uploaded_at` = current timestamp
- `uploaded_by_sangha_sevi_pk` = authorized user
- `version` = initial version

---

# 17. Transition: Document ACTIVE -> INACTIVE

**Trigger:** Document superseded by newer version, or administratively
deactivated

**Preconditions:**
- Authorized user
- Business justification

**Effects:**
- `is_active` = FALSE
- `updated_at` = current timestamp

**Constraints:**
- Deactivated documents remain physically present
- Historical document records are preserved

---

# 18. Document Version Lifecycle

Where document versioning applies:

```text
Version 1 uploaded -> ACTIVE
Version 2 uploaded -> ACTIVE
Version 1 -> INACTIVE (superseded)
```

The version number increments with each new upload for the same document
type and Person.

---

# 19. Cross-Module Lifecycle Events

The Person Module publishes lifecycle events that downstream modules
must respond to according to their own rules:

| Person Event | Affected Modules | Expected Response |
|---|---|---|
| Death Recorded | Membership, Governance, Authentication, Finance | Module-specific termination/closure rules |
| Person Soft-Deleted | All referencing modules | Historical references preserved; no cascading delete |
| Person Restored | All referencing modules | References become operationally valid again |
| Person Merged | All referencing modules | FK references transferred to target Person |

The Person Module does not dictate downstream responses — each module
owns its own lifecycle rules (PER-BR-027).

---

# 20. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of Person records (PER-BR-071)
- Automatic merge without authorization (PER-BR-036)
- Death causing physical deletion (PER-BR-026)
- Membership cessation causing Person deletion (PER-BR-068)
- Organization change creating new Person (PER-BR-049)
- Attribute correction creating new Person (PER-BR-013/014/015)
- Duplicate Person from registration source (PER-BR-090/091/092)
```

---

# 21. Lifecycle and Audit Integration

All Person lifecycle transitions are auditable through the common
audit framework:

| Transition | Audit Fields |
|---|---|
| Registration | created_at, created_by_sangha_sevi_pk |
| Update | updated_at, updated_by_sangha_sevi_pk |
| Death Recorded | updated_at, updated_by_sangha_sevi_pk |
| Soft Delete | deleted_at, deleted_by_sangha_sevi_pk |
| Restore | updated_at, updated_by_sangha_sevi_pk |
| Merge | Full audit trail (separate mechanism) |

---

# 22. Lifecycle State Query Patterns

For implementation reference:

| Query Intent | Filter |
|---|---|
| All active persons | `is_active = TRUE` |
| Active living persons | `is_active = TRUE AND date_of_death IS NULL` |
| Active deceased persons | `is_active = TRUE AND date_of_death IS NOT NULL` |
| Soft-deleted persons | `is_active = FALSE` |
| All persons (including soft-deleted) | No filter on is_active |

---

# 23. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact event-publishing mechanism (sync vs async)
Exact downstream notification protocol
Exact merge workflow steps and UI
Exact duplicate-scoring algorithm
Exact restore authorization workflow
Exact document versioning increment logic
```

---

# 24. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
1.0.0
```
