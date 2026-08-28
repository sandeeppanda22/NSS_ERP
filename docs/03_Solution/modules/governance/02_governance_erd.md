# NSS ERP — Governance Entity Relationship Design

**Document ID:** SOL-GOV-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Governance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
Governance Module.

The design is based on the frozen Unified Body Governance Model.

The model supports:

    Governing Bodies
    General Body
    Advisory Board
    Mahila Parichalana Mandali
    Sevak Sangha Executive
    Committees
    Position Assignment
    Acting Positions
    Elections

---

# 2. Core Governance Model

The frozen governance foundation is:

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

The source explicitly establishes this consolidated architecture.

---

# 3. High-Level ERD

```text
                       ┌──────────────────────┐
                       │  body_type_master    │
                       └──────────┬───────────┘
                                  │
                                  │ 1:N
                                  ▼
                       ┌──────────────────────┐
                       │     body_master      │
                       └──────────┬───────────┘
                                  │
                                  │ 1:N
                                  ▼
                    ┌────────────────────────────┐
                    │ body_member_assignment     │
                    └──────────┬─────────┬───────┘
                               │         │
                               │         │
                               ▼         ▼
                            Person    position_master
                                         │
                                         │
                                         ▼
                              position assignment
```

Acting assignments and elections extend this model:

```text
body_master
    │
    ├── body_member_assignment
    │
    ├── acting_position_assignment
    │
    └── election
            │
            ├── election_nomination
            │
            ├── election_vote
            │
            └── election_result
```

---

# 4. `body_type_master`

## Purpose

Defines the type/category of governance body.

Conceptually:

```text
body_type_master
        │
        │ 1:N
        ▼
body_master
```

---

# 5. Body Type Examples

The unified model supports body types such as:

```
KENDRA_GOVERNING_BODY
SAKHA_GOVERNING_BODY
ADVISORY_BOARD
MAHILA_PARICHALANA_MANDALI
SEVAK_SANGHA_EXECUTIVE
UPBS_COMMITTEE
```

These represent body classifications rather than individual bodies.

---

# 6. `body_master`

## Purpose

Represents an actual governance body.

Relationship:

```text
body_type_master
        1
        │
        N
        ▼
body_master
```

---

# 7. Body Examples

A `body_master` record may represent:

```text
Kendra Governing Body
Sakha Governing Body
Advisory Board
Mahila Parichalana Mandali
Sevak Sangha Executive
UPBS Registration Committee
```

The same schema supports all of them.

---

# 8. Body Type vs Body

The distinction is:

```text
Body Type
    =
classification

Body
    =
actual governance entity
```

Example:

```text
body_type_master
    SAKHA_GOVERNING_BODY

        ↓

body_master
    Sakha Governing Body — Sakha A
```

---

# 9. `position_master`

## Purpose

Defines reusable governance positions.

Conceptually:

```text
position_master
```

is referenced by governance assignments.

---

# 10. Position Examples

The frozen position catalogue includes:

```
PRESIDENT
VICE_PRESIDENT
PARICHALAK
SECRETARY
ASSISTANT_SECRETARY
TREASURER
MUKHYA_PUJAKA
MEMBER
```

The source confirms these positions as frozen.

---

# 11. Position Reuse

A position can be used by multiple governance bodies.

Conceptually:

```text
position_master
       │
       ├── Kendra Governing Body
       ├── Sakha Governing Body
       ├── Mahila Parichalana Mandali
       └── Other Approved Bodies
```

The position definition is therefore separate from the body.

---

# 12. `body_member_assignment`

## Purpose

Represents an actual person/member's assignment to a governance body.

Conceptually:

```text
body_master
     │
     ▼
body_member_assignment
     │
     ├── Person / Member
     │
     └── Position
```

---

# 13. Assignment Relationship

Logical model:

```text
body_master
      1
      │
      N
      ▼
body_member_assignment
      N
      │
      ├──────────────► Person / Member
      │
      └──────────────► position_master
```

---

# 14. Assignment History

The assignment entity supports historical governance membership.

Example:

```text
2023–2026
President = Person A

2026–2029
President = Person B

2029–2032
President = Person C
```

The source explicitly identifies historical tracking as a major benefit of
the unified model.

---

# 15. No Separate History Table

A separate:

```text
governance_member_history
```

is not required by the frozen Unified Body Governance Model.

Historical assignments are represented through the assignment model and its
effective lifecycle.

---

# 16. `acting_position_assignment`

## Purpose

Represents temporary/acting responsibility for a governance position.

Conceptually:

```text
body_master
     │
     ▼
acting_position_assignment
     │
     ├── Person
     └── Position
```

---

# 17. Acting vs Normal Assignment

The ERD deliberately distinguishes:

```text
Normal Governance Assignment
        ≠
Acting Position Assignment
```

An acting appointment does not erase the underlying governance assignment.

---

# 18. Acting Assignment History

Acting assignments must preserve:

```
Person
Body
Position
Effective Period
```

where required by the governance rules.

---

# 19. Person Relationship

Governance assignments ultimately identify a person/member.

Conceptually:

```text
Person
   │
   ▼
body_member_assignment
```

The authoritative Person and Membership models remain outside Governance.

---

# 20. Membership Boundary

Governance does not create a separate membership identity.

A governance participant continues to use the authoritative NSS membership
identity.

Governance assignment therefore references the existing Person/Membership
architecture.

---

# 21. `election`

## Purpose

Represents a governance election event/process.

Conceptually:

```text
body_master
     │
     ▼
election
```

An election is associated with the governance body or applicable governance
context.

---

# 22. Election Lifecycle

The logical election relationship is:

```text
body_master
     │
     ▼
election
     │
     ├── nominations
     ├── votes
     └── result
```

---

# 23. `election_nomination`

## Purpose

Represents nomination of an eligible candidate for an election.

Relationship:

```text
election
     │
     │ 1:N
     ▼
election_nomination
```

---

# 24. Nomination Candidate

A nomination identifies the candidate/person participating in the election.

The authoritative Person/Membership model remains the source of candidate
identity.

---

# 25. `election_vote`

## Purpose

Represents a recorded vote within an election.

Relationship:

```text
election
     │
     │ 1:N
     ▼
election_vote
```

---

# 26. Vote Identity

A vote must be associated with the election and the eligible voting member,
according to the applicable election rules.

The exact physical FK structure is finalized in Table Design.

---

# 27. `election_result`

## Purpose

Represents the outcome of an election.

Relationship:

```text
election
     │
     │ 1:1 / 1:N
     ▼
election_result
```

The exact cardinality depends on the final election-result model.

---

# 28. Election to Assignment

The logical governance flow is:

```text
Election
    │
    ▼
Election Result
    │
    ▼
Governance Assignment
```

The election result establishes the outcome.

The governance assignment establishes the resulting governance state.

---

# 29. Election Does Not Replace History

A new election result shall not overwrite historical governance assignments.

Example:

```text
Previous Assignment
       │
       ▼
Election
       │
       ▼
New Result
       │
       ▼
New Assignment
```

Previous governance history remains preserved.

---

# 30. Governing Body Structure

The main NSS governing-body model can be represented as:

```text
body_type_master
        │
        ▼
body_master
        │
        ▼
body_member_assignment
        │
        ▼
position_master
```

---

# 31. Kendra Governing Body

Conceptually:

```text
body_type_master
    KENDRA_GOVERNING_BODY
            │
            ▼
body_master
    Kendra Governing Body
            │
            ▼
body_member_assignment
            │
      ┌─────┴─────┐
      ▼           ▼
   Person     Position
```

---

# 32. Sakha Governing Body

Conceptually:

```text
body_type_master
    SAKHA_GOVERNING_BODY
            │
            ▼
body_master
    Sakha Governing Body
            │
            ▼
body_member_assignment
```

---

# 33. Advisory Board

Conceptually:

```text
body_type_master
    ADVISORY_BOARD
            │
            ▼
body_master
    Advisory Board
            │
            ▼
body_member_assignment
```

No separate advisory-board membership table is required.

---

# 34. Mahila Parichalana Mandali

Conceptually:

```text
body_type_master
    MAHILA_PARICHALANA_MANDALI
            │
            ▼
body_master
            │
            ▼
body_member_assignment
```

No separate Mahila governance membership table is required.

The source explicitly confirms the unified approach for Mahila governance.

---

# 35. Sevak Sangha Executive

Conceptually:

```text
body_type_master
    SEVAK_SANGHA_EXECUTIVE
            │
            ▼
body_master
            │
            ▼
body_member_assignment
```

The Sevak business rules currently mark executive positions, selection/
election and term duration as pending, so the ERD should not invent those
details here.

---

# 36. Future Committees

A future committee can be represented as:

```text
body_type_master
        │
        ▼
body_master
        │
        ▼
body_member_assignment
```

Example:

```text
UPBS_SECURITY_COMMITTEE
```

No schema redesign is required merely because the committee is new.

---

# 37. Unified Body Expansion

The architecture therefore supports:

```text
Today:

Kendra Governing Body
Sakha Governing Body
Advisory Board
Mahila Parichalana Mandali
Sevak Sangha Executive

Tomorrow:

UPBS Committees
Publication Committee
Finance Committee
Disciplinary Committee
Special Task Force
```

All use the same governance foundation.

---

# 38. Position Assignment

The conceptual relationship is:

```text
body_member_assignment
          │
          └──────► position_master
```

This means the assignment determines which position the person holds in
that body.

---

# 39. Multiple Positions

The ERD permits the possibility of multiple assignments for a person where
the governance rules allow it.

Example:

```text
Person A
   │
   ├── President — Body A
   └── Secretary — Body B
```

Governance rules determine whether a specific combination is permissible.

---

# 40. Dual Office Holding

The frozen Mahila governance rules explicitly allow a female member to
simultaneously serve on:

```
Main Governing Body
Mahila Parichalana Mandali
```

where elected/selected to both.

The unified assignment model supports this naturally.

---

# 41. Organizational Scope

Governance bodies are associated with the appropriate organizational
context.

Conceptually:

```text
Organization
      │
      ▼
body_master
```

The exact physical Organization FK depends on the finalized Organization
schema.

This ERD does not invent an unsupported FK column.

---

# 42. Governance and Geography

Governance scope may have geographic context, but geography and organization
remain separate.

```text
Geography
   ≠
Organization
   ≠
Governance Body
```

---

# 43. Governance and RBAC

Governance positions are not automatically application roles.

Therefore:

```text
position_master
      ≠
role_master
```

Application roles remain under Administration/RBAC.

---

# 44. Governance and Authentication

Authentication remains outside the Governance ERD.

Governance users authenticate through the common:

```text
user_account
```

architecture.

---

# 45. Governance and Membership

Membership remains outside the Governance ERD.

Governance consumes the authoritative Person/Membership identity.

---

# 46. Governance and Audit

Governance changes use the common Audit framework.

The ERD does not introduce:

```text
governance_audit
```

---

# 47. Governance History

Historical governance state is represented through:

```text
body_member_assignment
acting_position_assignment
election
election_result
```

as applicable.

---

# 48. No Body-Specific Tables

The following are explicitly NOT part of the current Unified Body ERD:

```text
governing_body_member
advisory_board_member
mahila_member
sevak_member
committee_member
```

They were conceptually replaced by:

```text
body_member_assignment
```

This consolidation is frozen.

---

# 49. No Body-Specific Position Tables

The following are also not introduced:

```text
governing_body_position
advisory_board_position
committee_position
mahila_position
```

The reusable:

```text
position_master
```

is authoritative.

---

# 50. No Separate Mahila Governance Schema

Mahila Parichalana Mandali uses:

```text
body_type_master
body_master
body_member_assignment
position_master
```

rather than a separate Mahila governance schema.

---

# 51. Complete Logical ERD

```text
                         ┌──────────────────────┐
                         │  body_type_master    │
                         └──────────┬───────────┘
                                    │
                                    │ 1:N
                                    ▼
                         ┌──────────────────────┐
                         │     body_master      │
                         └───────┬───────┬──────┘
                                 │       │
                           1:N   │       │ 1:N
                                 │       │
                                 ▼       ▼
                 ┌──────────────────┐  ┌────────────────────────┐
                 │body_member_      │  │acting_position_        │
                 │assignment        │  │assignment              │
                 └──────┬─────┬────┘   └──────────┬─────────────┘
                        │     │                    │
                        │     └───────┐            │
                        ▼             ▼            ▼
                     Person    position_master   Person
                                      ▲
                                      │
                                      └───────────────┐
                                                      │
                                             Position assignment


                         ┌──────────────────────┐
                         │       election       │
                         └───────┬─────┬────────┘
                                 │     │
                           1:N   │     │ 1:N
                                 ▼     ▼
                      ┌──────────────┐ ┌──────────────┐
                      │ election_    │ │ election_vote│
                      │ nomination   │ └──────────────┘
                      └──────────────┘
                                 │
                                 │
                                 ▼
                       ┌──────────────────┐
                       │ election_result  │
                       └────────┬─────────┘
                                │
                                ▼
                    New Governance Assignment
```

---

# 52. Relationship Matrix

| Source             | Target                       | Relationship        | Status                       |
| ------------------ | ---------------------------- | ------------------- | ---------------------------- |
| `body_type_master` | `body_master`                | 1:N                 | Frozen architecture          |
| `body_master`      | `body_member_assignment`     | 1:N                 | Frozen architecture          |
| `position_master`  | `body_member_assignment`     | 1:N                 | Frozen architecture          |
| Person/Member      | `body_member_assignment`     | 1:N                 | Logical                      |
| `body_master`      | `acting_position_assignment` | 1:N                 | Frozen architecture          |
| Person/Member      | `acting_position_assignment` | 1:N                 | Logical                      |
| `position_master`  | `acting_position_assignment` | 1:N                 | Logical                      |
| `body_master`      | `election`                   | 1:N                 | Logical                      |
| `election`         | `election_nomination`        | 1:N                 | Frozen election architecture |
| `election`         | `election_vote`              | 1:N                 | Frozen election architecture |
| `election`         | `election_result`            | Result relationship | Frozen election architecture |
| `election_result`  | Governance Assignment        | Logical workflow    | Source-aligned               |

---

# 53. Relationship Not Assumed

The following physical relationships are deliberately not frozen here:

```text
body_master → specific Organization table
election → specific Organization table
election_result → body_member_assignment
```

The logical relationship exists where supported, but the exact physical FK
must be finalized in Table Design.

---

# 54. Historical Governance Model

The unified model allows:

```text
Body
  │
  └── Assignments over time
          │
          ├── 2023–2026 → Person A
          ├── 2026–2029 → Person B
          └── 2029–2032 → Person C
```

No separate body-specific history tables are required.

---

# 55. Election-to-History Model

```text
Previous Governance State
          │
          ▼
       Election
          │
          ▼
   Election Result
          │
          ▼
New Governance State
```

Previous state remains historically available.

---

# 56. Future-Proofing

The primary benefit of this ERD is that new governance bodies become data,
not schema changes.

```text
New Body
   ↓
New body_master record
   ↓
Existing assignment model
   ↓
Existing position model
```

---

# 57. DDL Boundary

This ERD does not define:

```
Exact column lists
Exact data types
Exact FK names
Exact constraints
Exact indexes
Election vote secrecy implementation
Exact term fields
Exact effective-date fields
```

These belong to Business Rules and Table Design.

---

# 58. Current Governance Entity Set

Core unified governance:

```text
body_type_master
body_master
position_master
body_member_assignment
acting_position_assignment
```

Related election entities:

```text
election
election_nomination
election_vote
election_result
```

---

# 59. Source Alignment

The project source explicitly states that the Unified Body Governance Model
replaced separate:

```text
governing_body_member
advisory_board_member
mahila_member
sevak_member
committee_member
```

with:

```text
body_master
body_member_assignment
position_master
body_type_master
acting_position_assignment
```

and identifies the four election entities as related Governance structures.

The project module division independently identifies Governance as covering
General Body, Governing Body, Advisory Board, Mahila Parichalana Mandali,
Committees, Position Assignment and Election Management.

---

# 60. Status

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
