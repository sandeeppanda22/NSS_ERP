# NSS ERP — Governance Table Design

**Document ID:** SOL-GOV-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Governance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the table-level design baseline for the Governance
Module.

The design follows the frozen Unified Body Governance Model.

The Governance foundation consists of:

    body_type_master
    body_master
    position_master
    body_member_assignment
    acting_position_assignment

Related election entities are:

    election
    election_nomination
    election_vote
    election_result

---

# 2. Important Architecture Decision

The following older structures are NOT part of the current frozen design:

    governing_body
    governing_body_member
    advisory_board
    advisory_board_member
    mahila_member
    sevak_member
    committee_member

They were replaced conceptually by the Unified Body Governance Model.

---

# 3. Current Table Inventory

| # | Table | Purpose |
|---:|---|---|
| 1 | `body_type_master` | Governance body classification |
| 2 | `body_master` | Actual governance body |
| 3 | `position_master` | Reusable governance positions |
| 4 | `body_member_assignment` | Person/member governance assignment |
| 5 | `acting_position_assignment` | Temporary acting assignment |
| 6 | `election` | Governance election |
| 7 | `election_nomination` | Election candidate nomination |
| 8 | `election_vote` | Recorded election vote |
| 9 | `election_result` | Election outcome |

---

# 4. Common Database Standards

Governance tables shall follow the project-wide database standards.

Technical primary keys shall use:

    <table_name>_pk

UUID technical primary keys are used by the project database architecture.

Where applicable, common lifecycle/audit fields shall follow the project
database standards.

---

# 5. `body_type_master`

## 5.1 Purpose

Defines the classification/type of governance body.

Examples include:

    KENDRA_GOVERNING_BODY
    SAKHA_GOVERNING_BODY
    ADVISORY_BOARD
    MAHILA_PARICHALANA_MANDALI
    SEVAK_SANGHA_EXECUTIVE
    COMMITTEE

---

## 5.2 Primary Key

Required:

    body_type_master_pk UUID PRIMARY KEY

---

## 5.3 Logical Attributes

The table requires:

    body_type_code
    body_type_name
    description
    is_active

Exact lengths remain subject to final DDL standards.

---

## 5.4 Body Type Code

`body_type_code` shall be stable and unique.

Example:

    MAHILA_PARICHALANA_MANDALI

---

## 5.5 Body Type Uniqueness

Duplicate body-type codes shall not be permitted.

---

## 5.6 Body Type Lifecycle

A body type that has been used historically should not be physically
deleted merely because it is no longer used for new bodies.

---

# 6. `body_master`

## 6.1 Purpose

Represents an actual governance body.

Examples:

    Kendra Governing Body
    Sakha Governing Body
    Advisory Board
    Mahila Parichalana Mandali
    Sevak Sangha Executive
    UPBS Registration Committee

---

## 6.2 Primary Key

Required:

    body_master_pk UUID PRIMARY KEY

---

## 6.3 Foreign Key

Required:

    body_type_master_pk

References:

    body_type_master.body_type_master_pk

---

## 6.4 Logical Attributes

The table requires a representation of:

    body_master_pk
    body_type_master_pk
    body_code
    body_name
    description
    organizational_scope
    effective_from
    effective_to
    is_active

The exact organization-scope FK is finalized against the Organization
schema.

---

## 6.5 Body Code

Each actual governance body should have a stable business code.

The code shall be unique within the applicable governance namespace.

---

## 6.6 Body Identity

A body record represents the actual governance entity.

Its identity should not change merely because office holders change.

---

## 6.7 Body Lifecycle

A body may be:

    Created
    Active
    Reconstituted
    Historical

Exact status representation shall follow the final table design.

---

# 7. `position_master`

## 7.1 Purpose

Defines reusable governance positions.

Frozen examples include:

    PRESIDENT
    VICE_PRESIDENT
    PARICHALAK
    SECRETARY
    ASSISTANT_SECRETARY
    TREASURER
    MUKHYA_PUJAKA
    MEMBER

---

## 7.2 Primary Key

Required:

    position_master_pk UUID PRIMARY KEY

---

## 7.3 Logical Attributes

The table requires:

    position_code
    position_name
    description
    display_order
    is_active

---

## 7.4 Position Code

Position codes shall be stable and unique.

---

## 7.5 Position Reuse

A position shall be reusable across multiple governance bodies where the
applicable governance rules permit it.

---

## 7.6 Position Does Not Equal RBAC Role

A governance position shall not contain application permission information.

Therefore:

    position_master

is separate from:

    role_master

---

# 8. `body_member_assignment`

## 8.1 Purpose

Records the assignment of a person/member to a governance body and position.

This is the core transaction table of the Unified Body Governance Model.

---

## 8.2 Primary Key

Required:

    body_member_assignment_pk UUID PRIMARY KEY

---

## 8.3 Logical Foreign Keys

The table requires references to:

    body_master
    position_master
    Person / Membership identity

Conceptually:

    body_master_pk
    position_master_pk
    person_pk / sangha_sevi_pk

The exact identity FK must follow the finalized Person/Membership schema.

---

## 8.4 Logical Attributes

The table requires a representation of:

    body_member_assignment_pk
    body_master_pk
    position_master_pk
    person/membership identity
    effective_from
    effective_to
    assignment_status
    assignment_reference
    created_at
    updated_at

The exact column naming is subject to final SQL standards.

---

## 8.5 Assignment History

Assignments shall be retained historically.

Example:

    Person A
    President
    Body X
    2023-2026

    Person B
    President
    Body X
    2026-2029

Both records remain available.

---

## 8.6 No Historical Overwrite

A new assignment shall not update an old assignment in a way that destroys
historical information.

---

## 8.7 Effective Period

An assignment should have an identifiable effective period.

At minimum:

    effective_from

and, where applicable:

    effective_to

---

## 8.8 Active Assignment

Current assignment state shall be determinable from the assignment period
and/or approved status model.

---

## 8.9 Position Occupancy

The database design should support validation of applicable body/position
composition rules.

For example, where a body requires one President, the system must not allow
multiple simultaneously active Presidents unless the applicable governance
rule explicitly permits it.

---

## 8.10 Historical Assignments

Historical assignments remain queryable for:

    Governance Reports
    Historical Office Holders
    Audit
    Election History
    Governance Analysis

---

# 9. `acting_position_assignment`

## 9.1 Purpose

Represents temporary acting responsibility.

---

## 9.2 Primary Key

Required:

    acting_position_assignment_pk UUID PRIMARY KEY

---

## 9.3 Logical Foreign Keys

The table should reference:

    body_master
    position_master
    Person / Membership identity

---

## 9.4 Logical Attributes

The table requires:

    acting_position_assignment_pk
    body_master_pk
    position_master_pk
    person/membership identity
    effective_from
    effective_to
    reason
    status

---

## 9.5 Acting Assignment Independence

An acting assignment shall be separate from the normal assignment.

---

## 9.6 Acting Does Not Replace Normal Assignment

Creating an acting assignment shall not delete or overwrite the normal
office-holder history.

---

# 10. `election`

## 10.1 Purpose

Represents a governance election.

---

## 10.2 Primary Key

Required:

    election_pk UUID PRIMARY KEY

---

## 10.3 Logical Foreign Key

An election is associated with:

    body_master

through:

    body_master_pk

---

## 10.4 Logical Attributes

The table requires a representation of:

    election_pk
    body_master_pk
    election_code
    election_name
    election_type
    nomination_start
    nomination_end
    voting_start
    voting_end
    status
    result_date

The exact fields depend on the final election rules.

---

## 10.5 Election Identity

Each election shall have a stable unique identity.

---

## 10.6 Election Lifecycle

Conceptually:

    Planned
       ↓
    Nomination
       ↓
    Voting
       ↓
    Counting
       ↓
    Result
       ↓
    Completed

The final status catalogue is subject to election design.

---

# 11. `election_nomination`

## 11.1 Purpose

Represents a candidate nomination within an election.

---

## 11.2 Primary Key

Required:

    election_nomination_pk UUID PRIMARY KEY

---

## 11.3 Logical Foreign Keys

The nomination should reference:

    election
    candidate Person/Membership identity
    position where the election is position-specific

---

## 11.4 Logical Attributes

The table requires:

    election_nomination_pk
    election_pk
    candidate identity
    position_master_pk
    nomination_date
    nomination_status
    proposer identity
    eligibility_status

Exact fields depend on the final election workflow.

---

## 11.5 Candidate Uniqueness

The same candidate shall not be duplicated for the same election/position
where the applicable election rules prohibit duplicate nominations.

---

# 12. `election_vote`

## 12.1 Purpose

Records a vote associated with an election.

---

## 12.2 Primary Key

Required:

    election_vote_pk UUID PRIMARY KEY

---

## 12.3 Logical Foreign Keys

The vote is associated with:

    election
    voter Person/Membership identity

Where the election is candidate/position specific, the vote also requires
the applicable candidate/nomination reference.

---

## 12.4 Logical Attributes

The table requires a representation of:

    election_vote_pk
    election_pk
    voter identity
    nomination/candidate reference
    vote_timestamp
    vote_status

---

## 12.5 One-Vote Rule

Where the applicable election rule is one-member-one-vote, database/API
constraints shall prevent a member from casting multiple valid votes for the
same election.

---

## 12.6 Vote Integrity

Votes shall not be casually modified after the election enters a finalized
state.

The exact immutability and correction workflow is finalized in election
implementation design.

---

# 13. `election_result`

## 13.1 Purpose

Stores the outcome of an election.

---

## 13.2 Primary Key

Required:

    election_result_pk UUID PRIMARY KEY

---

## 13.3 Logical Foreign Keys

The result references:

    election

and, where required:

    candidate/nomination
    position

---

## 13.4 Logical Attributes

The table requires a representation of:

    election_result_pk
    election_pk
    position_master_pk
    winning nomination/candidate
    result status
    vote count where applicable
    declared_at
    declared_by

---

## 13.5 Result History

Election results shall remain historically available.

---

## 13.6 Result Finalization

Once officially finalized, an election result shall not be silently
overwritten.

Any correction must follow the approved correction/audit process.

---

# 14. Election → Assignment

An election result may result in a new:

    body_member_assignment

The assignment is the authoritative governance state.

The election result remains the historical election outcome.

---

# 15. Governance Identity Relationships

The logical identity flow is:

```text
Person
   │
   ▼
Membership
   │
   ▼
Governance Assignment
```

Governance does not create a second Person or Membership identity.

---

# 16. Organization Relationship

`body_master` must be associated with the applicable organizational scope
where required.

The exact FK shall reference the frozen Organization model.

No new Organization structure shall be introduced in Governance.

---

# 17. Governance Scope

Possible governance scopes include:

```
Kendra
Sakha
Other approved organizational scope
```

The actual scope must be represented using the authoritative Organization
model.

---

# 18. Mahila Parichalana Mandali

Mahila Parichalana Mandali uses the same tables:

```
body_type_master
body_master
position_master
body_member_assignment
acting_position_assignment
```

No Mahila-specific governance tables shall be created.

---

# 19. Mahila Body Type

The body type catalogue shall include:

```
MAHILA_PARICHALANA_MANDALI
```

where this code is the approved final representation.

---

# 20. Mahila Composition

The frozen project rule is:

```
9 members
```

Positions:

```
President
Vice President
Secretary
Assistant Secretary
Treasurer
Members
```

The remaining seats are represented through normal assignments.

---

# 21. Mahila Eligibility

Eligibility rules require:

```
Female Members Only
```

for Mahila governance candidature/voting as applicable.

Eligibility is a business rule and must be enforced through the appropriate
Membership/Person information rather than by duplicating gender data in
Governance.

---

# 22. Mahila Term

The frozen project rule specifies:

```
3 Years
```

The assignment effective-period model should represent this term.

---

# 23. Mahila Dual Office Holding

The table design must permit the same eligible person to have assignments
in:

```
Main Governing Body
```

and:

```
Mahila Parichalana Mandali
```

where the governing rules permit it.

The unified assignment model naturally supports this.

---

# 24. Kendra Governing Body

The Kendra Governing Body is represented through:

```
body_type_master
body_master
position_master
body_member_assignment
```

The current source identifies the statutorily defined nine-member
structure.

---

# 25. Position Composition

The database should support validation of required composition without
hard-coding a separate table for every body.

Examples:

```
One President
One Vice-President
One Parichalak
One Secretary
One Assistant Secretary
One Treasurer
Remaining Member seats
```

The exact enforcement mechanism belongs to the final business/API design.

---

# 26. Advisory Board

The Advisory Board is represented through:

```
body_type_master
body_master
position_master
body_member_assignment
```

No:

```
advisory_board
advisory_board_member
```

tables are required.

---

# 27. Committees

Committees use:

```
body_type_master
body_master
position_master
body_member_assignment
```

A new approved committee should normally require master data rather than a
new table.

---

# 28. Sevak Sangha Executive

The Sevak Sangha Executive can use the unified Governance tables.

Any detailed Sevak-specific executive selection, term or eligibility rule
must follow the Sevak/Governance source and shall not be invented here.

---

# 29. Historical Integrity

Governance tables shall preserve historical information.

Applicable records shall use:

```
effective_from
effective_to
```

and/or an approved status model.

---

# 30. Audit Metadata

Applicable Governance tables should follow the project-standard audit
metadata:

```
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk

is_active
```

The exact applicability must be finalized per table.

---

# 31. Soft Delete

Historical Governance records shall not be physically deleted merely to
remove them from current operational views.

Where soft deletion is appropriate, it shall follow project standards.

---

# 32. Delete Behaviour

Foreign-key delete behaviour shall protect historical governance data.

Cascading deletes must not silently remove:

```
Historical Assignments
Election History
Election Results
Acting Assignments
```

The exact PostgreSQL `ON DELETE` behaviour belongs to DDL.

---

# 33. Uniqueness

The final design should enforce appropriate uniqueness for:

```
body_type_code
body_code
position_code
election_code
```

and applicable composite business keys.

---

# 34. Assignment Constraints

The final database design should support integrity rules such as:

```
Valid Body
Valid Person
Valid Position
Valid Effective Period
```

and applicable body/position occupancy constraints.

---

# 35. Temporal Integrity

Assignment periods should not create impossible overlapping states.

For positions that allow only one active holder, overlapping active assignments
for the same:

```
Body
Position
```

must be prevented.

The exact PostgreSQL constraint/index strategy is finalized during DDL.

---

# 36. Acting Assignment Constraints

An acting assignment must have:

```
Valid Body
Valid Position
Valid Person
Valid Effective Period
```

and should not silently contradict the underlying governance state.

---

# 37. Election Constraints

An election shall reference a valid governance body.

Nomination shall reference a valid election.

Vote shall reference a valid election and eligible voter.

Result shall reference a valid election.

---

# 38. Election Vote Uniqueness

For elections using one-member-one-vote:

```
election_pk
voter_identity
```

shall form the logical uniqueness boundary.

The final database implementation must enforce this where applicable.

---

# 39. Candidate/Position Constraints

Where an election is position-specific, a candidate nomination should be
associated with the relevant position.

The exact composite uniqueness depends on the election rules.

---

# 40. Result Constraints

An election shall not have conflicting finalized results for the same
position.

The final implementation must enforce the applicable uniqueness rule.

---

# 41. Governance Position vs RBAC

No FK shall be introduced from:

```
position_master
```

to:

```
role_master
```

simply because both contain the concept of a role/position.

Governance position and application role are different domains.

---

# 42. Governance vs Membership

No duplicate Membership table shall be created in Governance.

The authoritative Membership table remains:

```
sangha_sevi
```

and related Membership structures.

---

# 43. Governance vs Person

No duplicate Person table shall be created in Governance.

The authoritative Person record remains in the Person Module.

---

# 44. Governance vs Organization

No duplicate organizational hierarchy shall be created in Governance.

Governance references the Organization model.

---

# 45. Governance Table Relationships

```text
body_type_master
        │
        │ 1:N
        ▼
body_master
        │
        ├───────────────┐
        │               │
        │ 1:N           │ 1:N
        ▼               ▼
body_member_       acting_position_
assignment         assignment
        │               │
        ├──────┐        ├──────┐
        │      │        │      │
        ▼      ▼        ▼      ▼
     Person Position   Person Position


body_master
     │
     │ 1:N
     ▼
election
     │
     ├──< election_nomination
     │
     ├──< election_vote
     │
     └──< election_result
```

---

# 46. Table Ownership

| Table                        | Ownership  |
| ---------------------------- | ---------- |
| `body_type_master`           | Governance |
| `body_master`                | Governance |
| `position_master`            | Governance |
| `body_member_assignment`     | Governance |
| `acting_position_assignment` | Governance |
| `election`                   | Governance |
| `election_nomination`        | Governance |
| `election_vote`              | Governance |
| `election_result`            | Governance |

---

# 47. Tables Explicitly Not Used

The current frozen design does not use:

```
governing_body
governing_body_member
advisory_board
advisory_board_member
mahila_member
sevak_member
committee_member
position_assignment
```

where these represent the superseded governance architecture.

The current authoritative assignment table is:

```
body_member_assignment
```

---

# 48. Exact Column Values Not Invented

Where the source has not frozen:

```
VARCHAR lengths
exact status codes
exact election type codes
exact organization FK
exact Person/Membership FK
exact vote-secrecy implementation
```

this document does not silently invent them.

They must be finalized before PostgreSQL DDL.

---

# 49. SQL Boundary

This document does not contain PostgreSQL DDL.

The next implementation phase will translate the approved table design into
SQL after all unresolved physical design points are reviewed.

---

# 50. Current Governance Table Count

Unified Governance:

```
5 core tables
```

Related Elections:

```
4 tables
```

Total:

```
9 tables
```

```text
1. body_type_master
2. body_master
3. position_master
4. body_member_assignment
5. acting_position_assignment
6. election
7. election_nomination
8. election_vote
9. election_result
```

---

# 51. Source Alignment

The uploaded PostgreSQL schema review confirms the later frozen refactoring:

Removed conceptually:

```
governing_body_member
advisory_board_member
mahila_member
sevak_member
committee_member
```

Replaced with:

```
body_master
body_member_assignment
position_master
body_type_master
acting_position_assignment
```

and retains the four election entities:

```
election
election_nomination
election_vote
election_result
```

The same source confirms the Unified Body Governance Model is intended to
support current bodies and future committees without schema changes.

The Mahila governance source confirms:

```
9 members
President
Vice President
Secretary
Assistant Secretary
Treasurer
Members
Female eligibility
Selection + Election
One Member → One Vote → One Candidate
3-year term
Dual office holding permitted
```

---

# 52. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
