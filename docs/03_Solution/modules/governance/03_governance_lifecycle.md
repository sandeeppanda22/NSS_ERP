# NSS ERP — Governance Lifecycle

**Document ID:** SOL-GOV-005  
**Version:** 0.1.0  
**Status:** DRAFT  
**Module:** Governance  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the Governance
Module entities:

- `body_type_master`
- `body_master`
- `position_master`
- `body_member_assignment`
- `acting_position_assignment`
- `election`
- `election_nomination`
- `election_vote`
- `election_result`

The Governance lifecycle is independent of Membership lifecycle.

---

# 2. Source Authority

This lifecycle document is governed by:

- Governance Module Overview (SOL-GOV-001)
- Governance ERD (SOL-GOV-002)
- Governance Business Rules (SOL-GOV-003)
- Governance Table Design (SOL-GOV-004)
- Person Lifecycle (SOL-PER-005)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. Body Type — Lifecycle

## States

```text
ACTIVE          is_active=TRUE
INACTIVE        is_active=FALSE
```

## Transitions

```text
CREATION -> ACTIVE -> Deactivate -> INACTIVE -> Reactivate -> ACTIVE
```

A body type that has been used historically should not be physically
deleted merely because it is no longer used for new bodies (Table Design
Section 5.6).

---

# 4. Body Master — Lifecycle States

```text
CREATED         is_active=TRUE, effective_from=SET, effective_to=NULL, status=CREATED
ACTIVE          is_active=TRUE, effective_from=SET, effective_to=NULL, status=ACTIVE
RECONSTITUTED   is_active=TRUE, effective_from=SET, effective_to=NULL, status=RECONSTITUTED
HISTORICAL      is_active=FALSE, effective_to=SET, status=HISTORICAL
```

---

# 5. Body State Definitions

## CREATED

The governance body record exists but has not yet begun active governance
operations. Positions may be defined but assignments may not yet be active.

## ACTIVE

The governance body is operationally current. Position assignments are
active. Elections may be conducted.

## RECONSTITUTED

The governance body has been reconstituted (new term, new composition)
while retaining its persistent identity. Previous assignments become
historical; new assignments are created.

## HISTORICAL

The governance body is no longer operationally active. All records remain
for historical reference, reporting, and audit.

---

# 6. Body State Transition Diagram

```text
              FORMED (Creation)
                     |
                     v
                  CREATED
                     |
              Activation
                     |
                     v
                  ACTIVE
                 /       \
   Reconstitution         Dissolution
               /               \
              v                 v
       RECONSTITUTED       HISTORICAL
              |
         (operates as ACTIVE)
              |
         Dissolution
              |
              v
          HISTORICAL
```

---

# 7. Transition: Formation -> CREATED

**Trigger:** New governance body defined

**Preconditions:**
- Valid `body_type_master_pk` reference
- Valid organizational scope reference (where applicable)
- `body_code` unique within governance namespace (GOV-BR-007)
- Authorized user

**Effects:**
- `body_master_pk` assigned (UUID)
- `body_code` assigned
- `is_active` = TRUE
- `effective_from` = creation date
- `effective_to` = NULL
- `created_at` = current timestamp

**Audit:** Body creation is audited (GOV-BR-062)

---

# 8. Transition: CREATED -> ACTIVE

**Trigger:** Governance body begins operations (positions assigned, quorum met)

**Preconditions:**
- Body has required position assignments (or activation criteria met)
- Authorized user

**Effects:**
- Status updated to ACTIVE
- `updated_at` = current timestamp

---

# 9. Transition: ACTIVE -> RECONSTITUTED

**Trigger:** Governance body reconstituted for new term

**Preconditions:**
- Election/selection process completed (where applicable)
- New term assignments ready
- Authorized user

**Effects:**
- Body status updated to RECONSTITUTED (then operates as ACTIVE)
- Previous assignments: `effective_to` = reconstitution date
- New assignments created with new `effective_from`
- Body identity (`body_master_pk`, `body_code`) unchanged (GOV-BR-007)
- `updated_at` = current timestamp

**Constraints:**
- Historical assignments preserved (GOV-BR-016, GOV-BR-017)
- Previous holders not overwritten (GOV-BR-017)

---

# 10. Transition: ACTIVE/RECONSTITUTED -> HISTORICAL

**Trigger:** Governance body dissolved or superseded

**Preconditions:**
- Authorized governance decision
- Business justification exists

**Effects:**
- `is_active` = FALSE
- `effective_to` = dissolution date
- Status = HISTORICAL
- All current assignments: `effective_to` = dissolution date
- `updated_at` = current timestamp

**Constraints:**
- Physical deletion prohibited (GOV-BR-063, GOV-BR-066)
- Historical assignments remain queryable (GOV-BR-016)
- Election history preserved (GOV-BR-040)

---

# 11. Position Master — Lifecycle

## States

```text
ACTIVE          is_active=TRUE
INACTIVE        is_active=FALSE
```

## Transitions

```text
CREATION -> ACTIVE -> Deactivate -> INACTIVE -> Reactivate -> ACTIVE
```

A position that has been used historically remains available for reporting.
Physical deletion is prohibited.

Position identity is independent of any specific body (GOV-BR-013).

---

# 12. Body Member Assignment — Lifecycle States

```text
ACTIVE          effective_from=SET, effective_to=NULL, assignment_status=ACTIVE
ENDED           effective_from=SET, effective_to=SET, assignment_status=ENDED
```

---

# 13. Assignment State Definitions

## ACTIVE

The person currently holds the governance position in the body. The
assignment is operationally current.

## ENDED

The assignment has concluded. The record remains as historical governance
information. The previous holder is determinable (GOV-BR-067).

---

# 14. Assignment State Transition Diagram

```text
              ASSIGNED (Creation)
                     |
                     v
                  ACTIVE
                 /   |   \
      Term End  /    |    \  Vacancy
              /      |      \
             v       v       v
          ENDED   ENDED    ENDED
                    (death)   (removal)
```

---

# 15. Transition: Assignment Creation -> ACTIVE

**Trigger:** Person assigned to governance body and position

**Preconditions:**
- Valid `body_master_pk` (body must be ACTIVE) (GOV-BR-072)
- Valid `position_master_pk` (GOV-BR-073)
- Valid Person/Membership identity (GOV-BR-074)
- Person satisfies applicable eligibility rules (GOV-BR-056)
- No conflicting active assignment for single-holder positions (GOV-BR-075)
- Authorized user

**Effects:**
- `body_member_assignment_pk` assigned (UUID)
- `effective_from` = assignment date
- `effective_to` = NULL
- `assignment_status` = ACTIVE
- `created_at` = current timestamp

**Audit:** Assignment is audited (GOV-BR-062)

---

# 16. Transition: ACTIVE -> ENDED (Normal Term End)

**Trigger:** Governance term expires or reconstitution occurs

**Preconditions:**
- Term period reached, or new term begins
- Authorized user

**Effects:**
- `effective_to` = end date
- `assignment_status` = ENDED
- `updated_at` = current timestamp

**Constraints:**
- Record remains physically present (GOV-BR-063)
- Historical holder determinable (GOV-BR-067)
- No overwrite of historical identity (GOV-BR-017)

---

# 17. Transition: ACTIVE -> ENDED (Vacancy)

**Trigger:** Position vacated (resignation, removal, death, disqualification)

**Preconditions:**
- Authorized governance decision or Person death event
- Business justification

**Effects:**
- `effective_to` = vacancy date
- `assignment_status` = ENDED
- `updated_at` = current timestamp

**Constraints:**
- Previous holder's history preserved (GOV-BR-051)
- Position remains valid even when unoccupied (GOV-BR-052)
- Vacancy may be filled through approved mechanism (GOV-BR-053)

---

# 18. Transition: ACTIVE -> ENDED (Person Death)

**Trigger:** Person death recorded in Person Module

**Effects:**
- All active governance assignments for deceased Person:
  - `effective_to` = date of death (or recording date)
  - `assignment_status` = ENDED
- Position becomes vacant
- Body composition updates accordingly
- Historical assignment fully preserved

The Governance Module responds to Person lifecycle events but does not
independently record death (GOV-BR-057).

---

# 19. Acting Position Assignment — Lifecycle States

```text
ACTIVE          effective_from=SET, effective_to=NULL, status=ACTIVE
ENDED           effective_from=SET, effective_to=SET, status=ENDED
```

---

# 20. Acting Assignment Transitions

## Transition: Creation -> ACTIVE

**Trigger:** Temporary acting responsibility assigned

**Preconditions:**
- Valid `body_master_pk` (body ACTIVE)
- Valid `position_master_pk`
- Valid Person/Membership identity
- Reason documented
- Authorized user

**Effects:**
- `acting_position_assignment_pk` assigned (UUID)
- `effective_from` = assignment date
- `effective_to` = NULL
- `status` = ACTIVE
- `created_at` = current timestamp

**Constraints:**
- Does not erase underlying normal assignment (GOV-BR-019)
- Normal position holder's history unchanged

## Transition: ACTIVE -> ENDED

**Trigger:** Acting period concludes (normal holder returns, permanent
appointment made, or acting period expires)

**Effects:**
- `effective_to` = end date
- `status` = ENDED
- `updated_at` = current timestamp

---

# 21. Election — Lifecycle States

```text
PLANNED         status=PLANNED
NOMINATION      status=NOMINATION
VOTING          status=VOTING
COUNTING        status=COUNTING
COMPLETED       status=COMPLETED
CANCELLED       status=CANCELLED
```

---

# 22. Election State Transition Diagram

```text
        PLANNED
           |
    Open Nominations
           |
           v
       NOMINATION
           |
    Close Nominations / Open Voting
           |
           v
        VOTING
           |
    Close Voting
           |
           v
       COUNTING
           |
    Declare Result
           |
           v
       COMPLETED
           |
    Result -> Assignment (separate transition)

    CANCELLED (terminal, reachable from PLANNED/NOMINATION/VOTING)
```

---

# 23. Transition: Election Creation -> PLANNED

**Trigger:** Election scheduled for a governance body

**Preconditions:**
- Valid `body_master_pk` (GOV-BR-038)
- Election code unique
- Authorized user

**Effects:**
- `election_pk` assigned (UUID)
- `election_code` assigned
- `status` = PLANNED
- `created_at` = current timestamp

---

# 24. Transition: PLANNED -> NOMINATION

**Trigger:** Nomination period opens

**Preconditions:**
- Election is in PLANNED state
- `nomination_start` date reached or manually triggered
- Authorized user

**Effects:**
- `status` = NOMINATION
- `updated_at` = current timestamp

---

# 25. Transition: NOMINATION -> VOTING

**Trigger:** Nomination period closed, voting opens

**Preconditions:**
- Election is in NOMINATION state
- At least one valid nomination exists (GOV-BR-046)
- `voting_start` date reached or manually triggered
- Authorized user

**Effects:**
- `status` = VOTING
- `updated_at` = current timestamp
- Nominations finalized (no new nominations accepted)

---

# 26. Transition: VOTING -> COUNTING

**Trigger:** Voting period closed

**Preconditions:**
- Election is in VOTING state
- `voting_end` date reached or manually triggered
- Authorized user

**Effects:**
- `status` = COUNTING
- `updated_at` = current timestamp
- No new votes accepted

---

# 27. Transition: COUNTING -> COMPLETED

**Trigger:** Results declared

**Preconditions:**
- Election is in COUNTING state
- `election_result` record(s) created
- Authorized user

**Effects:**
- `status` = COMPLETED
- `result_date` = declaration date
- `updated_at` = current timestamp

**Constraints:**
- Result is historical (GOV-BR-048)
- Result does not overwrite previous results (GOV-BR-049)

---

# 28. Transition: COMPLETED -> Assignment

**Trigger:** Election result leads to governance assignment

**Process:**
```text
Election COMPLETED
       |
Result declared (winner identified)
       |
New body_member_assignment created (ACTIVE)
       |
Previous holder assignment ended (if applicable)
```

The assignment is the authoritative governance state.
The election result remains the historical election outcome.

---

# 29. Transition: Any Pre-Completion -> CANCELLED

**Trigger:** Election cancelled before completion

**Preconditions:**
- Election is in PLANNED, NOMINATION, or VOTING state
- Authorized governance decision

**Effects:**
- `status` = CANCELLED
- `updated_at` = current timestamp

**Constraints:**
- Cancelled election record preserved for audit
- No governance assignment results from cancelled election

---

# 30. Election Nomination — Lifecycle

## States

```text
SUBMITTED       nomination_status=SUBMITTED
ACCEPTED        nomination_status=ACCEPTED
REJECTED        nomination_status=REJECTED
WITHDRAWN       nomination_status=WITHDRAWN
```

## Transitions

```text
SUBMITTED -> ACCEPTED (eligibility verified)
SUBMITTED -> REJECTED (eligibility failed)
ACCEPTED  -> WITHDRAWN (candidate withdraws)
```

**Constraints:**
- Candidate uniqueness per election/position (GOV-BR-046)
- Eligibility checked before acceptance (GOV-BR-047)
- Nomination records preserved historically

---

# 31. Election Vote — Lifecycle

Election votes are append-only records.

**Creation Preconditions:**
- Election is in VOTING state
- Voter satisfies eligibility (GOV-BR-043)
- One-member-one-vote enforced where applicable (GOV-BR-044)
- Valid nomination/candidate reference

**Effects:**
- `election_vote_pk` assigned (UUID)
- `vote_timestamp` = current timestamp

**Constraints:**
- No duplicate valid votes per eligible voter per election (GOV-BR-044)
- Votes not casually modified after election finalized (GOV-BR-045)
- Vote records preserved historically

---

# 32. Election Result — Lifecycle

Election results are append-only records.

**Creation Preconditions:**
- Election is in COUNTING or COMPLETED state
- Valid election reference
- Authorized user (declaration authority)

**Effects:**
- `election_result_pk` assigned (UUID)
- `declared_at` = declaration timestamp
- `declared_by` = authorized user

**Constraints:**
- Result is historical — never silently overwritten (GOV-BR-048, GOV-BR-049)
- No conflicting finalized results for same position (Table Design Section 40)
- Corrections follow approved audit process

---

# 33. Selection + Election Model (Mahila)

For Mahila Parichalana Mandali (GOV-BR-035, GOV-BR-042):

```text
Consensus Attempt
       |
  Consensus Reached? --- Yes --- Direct Assignment (no election)
       |
      No
       |
Election Triggered
       |
Normal Election Lifecycle (PLANNED -> COMPLETED)
       |
Assignment Created
```

The same unified tables handle both paths. Selection (consensus) results
in direct `body_member_assignment` creation without election records.

---

# 34. Mahila Term Lifecycle

Mahila Parichalana Mandali operates on a 3-year term (GOV-BR-036):

```text
Term Start (effective_from)
       |
    3 Years
       |
Term End (effective_to = effective_from + 3 years)
       |
New election/selection cycle
       |
New assignments created
       |
Previous assignments ended
```

---

# 35. Cross-Module Lifecycle Events

## Events Governance Responds To

| Source Event | Source Module | Governance Response |
|---|---|---|
| Person Death Recorded | Person | End all active assignments for deceased; positions become vacant |
| Person Soft-Deleted | Person | Historical assignments preserved as references |
| Person Merged | Person | FK references transferred to target Person |
| Membership Terminated | Membership | Eligibility may be affected (module-specific rules) |

## Events Governance Generates

| Governance Event | Affected Modules | Expected Response |
|---|---|---|
| Assignment Created | Administration (RBAC review) | Permission evaluation may trigger |
| Assignment Ended | Administration (RBAC review) | Permission evaluation may trigger |
| Body Dissolved | Reports (display) | Dashboard/reporting views update |
| Election Completed | Notification (if applicable) | Notifications may be sent |

---

# 36. Person Death and Governance

When a Person's death is recorded (Person Module event):

- All active `body_member_assignment` for deceased Person:
  - `effective_to` = date of death (or recording date)
  - `assignment_status` = ENDED
- All active `acting_position_assignment` for deceased Person:
  - `effective_to` = date of death
  - `status` = ENDED
- Affected positions become vacant
- Body composition rules may trigger vacancy-filling process
- Historical records fully preserved

The Governance Module does not independently record death — it responds
to the Person lifecycle event.

---

# 37. Vacancy Lifecycle

```text
Position Occupied (ACTIVE assignment exists)
       |
Vacancy Event (term end, death, resignation, removal)
       |
Position Vacant (no ACTIVE assignment for body+position)
       |
Vacancy-Filling Process (election/selection/appointment)
       |
New Assignment Created (ACTIVE)
       |
Position Occupied Again
```

**Constraints:**
- Vacancy does not delete the position (GOV-BR-052)
- Previous holder's history preserved (GOV-BR-051)
- Filling follows applicable governance mechanism (GOV-BR-053)

---

# 38. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of governance body records (GOV-BR-063, GOV-BR-066)
- Physical deletion of historical assignments (GOV-BR-063)
- Physical deletion of election records (GOV-BR-040)
- Physical deletion of election results (GOV-BR-048)
- Overwriting historical assignment identity (GOV-BR-017)
- Overwriting previous election results (GOV-BR-049)
- New assignment destroying previous holder's record (GOV-BR-017)
- Acting assignment erasing normal assignment (GOV-BR-019)
- Governance creating duplicate Person (GOV-BR-057)
- Governance creating/modifying Membership (GOV-BR-055)
- Governance creating duplicate organization hierarchy (Table Design Section 44)
- Position granting application permissions directly (GOV-BR-014, GOV-BR-061)
- Software inventing statutory governance rules (GOV-BR-093)
```

---

# 39. Lifecycle and Audit Integration

All Governance lifecycle transitions are auditable (GOV-BR-062):

| Transition | Audit Fields |
|---|---|
| Body Creation | created_at, created_by_sangha_sevi_pk |
| Body Status Change | updated_at, updated_by_sangha_sevi_pk |
| Body Dissolution | updated_at (+ effective_to set) |
| Assignment Creation | created_at, created_by_sangha_sevi_pk |
| Assignment End | updated_at, updated_by_sangha_sevi_pk |
| Acting Assignment Creation | created_at, created_by_sangha_sevi_pk |
| Acting Assignment End | updated_at, updated_by_sangha_sevi_pk |
| Election Creation | created_at |
| Election State Change | updated_at |
| Nomination | created_at |
| Vote | vote_timestamp |
| Result Declaration | declared_at, declared_by |

---

# 40. Lifecycle State Query Patterns

| Query Intent | Filter |
|---|---|
| Active governance bodies | `body_master.is_active = TRUE` |
| Historical bodies | `body_master.is_active = FALSE` |
| Current position holders | `body_member_assignment.effective_to IS NULL AND assignment_status = 'ACTIVE'` |
| Historical holders for a body | `body_member_assignment.body_master_pk = ? AND effective_to IS NOT NULL` |
| Current acting assignments | `acting_position_assignment.effective_to IS NULL AND status = 'ACTIVE'` |
| Vacant positions | Position in body with no ACTIVE assignment |
| Active elections | `election.status NOT IN ('COMPLETED', 'CANCELLED')` |
| Election history for a body | `election.body_master_pk = ?` |
| Holders during a period | `effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)` |

---

# 41. Temporal Integrity Rules

- For single-holder positions: no overlapping ACTIVE assignments for same
  body + position (Table Design Section 35)
- Assignment `effective_from` must not be after `effective_to`
- Acting assignment period must not extend beyond what is reasonable
- Election phases must follow sequential order (no skipping states)
- Body `effective_from` must precede any assignment `effective_from` for
  that body

---

# 42. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact body status vocabulary beyond CREATED/ACTIVE/RECONSTITUTED/HISTORICAL
Exact vacancy detection mechanism (query vs trigger)
Exact Person-death event consumption mechanism (sync vs async)
Exact election date validation rules
Exact nomination eligibility verification workflow
Exact vote secrecy implementation
Exact consensus/selection workflow for Mahila
Exact vacancy-filling authorization workflow
Exact notification mechanism for governance events
Exact term-expiry detection and alert mechanism
```

---

# 43. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
0.1.0
```
