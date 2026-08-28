# NSS ERP — Governance Module Overview

**Document ID:** SOL-GOV-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Governance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Governance Module manages the formal governance structures and
governance-related organizational responsibilities represented within NSS
ERP.

The module provides a unified architecture for:

    Governing Bodies
    General Body
    Advisory Board
    Mahila Parichalana Mandali
    Committees
    Position Assignment
    Acting Positions
    Elections

---

# 2. Core Governance Principle

NSS ERP uses the:

    Unified Body Governance Model

This model provides one reusable governance architecture instead of creating
separate database structures for every governing body or committee.

---

# 3. Unified Body Governance Model

The unified model is based on:

    body_type_master
    body_master
    position_master
    body_member_assignment
    acting_position_assignment

This allows different governance bodies to use the same underlying
architecture.

The source explicitly identifies this model as the frozen governance
foundation.

---

# 4. Governance Bodies

The same architecture supports existing and future bodies.

Current examples include:

    Kendra Governing Body
    Sakha Governing Body
    Advisory Board
    Mahila Parichalana Mandali
    Sevak Sangha Executive

Future bodies can also use the same model.

Examples:

    UPBS Central Committee
    UPBS Registration Committee
    UPBS Accommodation Committee
    Security Committee
    Publication Committee
    Finance Committee
    Disciplinary Committee
    Special Task Force

No separate schema is required merely because a new body is introduced.

---

# 5. Governance Module Scope

The Governance Module covers:

```text
Governance
│
├── Body Management
│
├── Position Management
│
├── Member Assignment
│
├── Acting Position Management
│
├── General Body
│
├── Advisory Board
│
├── Committees
│
└── Elections
```

---

# 6. Body Type

`body_type_master` defines the category/type of governance body.

Examples:

```
KENDRA_GOVERNING_BODY
SAKHA_GOVERNING_BODY
ADVISORY_BOARD
MAHILA_PARICHALANA_MANDALI
SEVAK_SANGHA_EXECUTIVE
UPBS_COMMITTEE
```

The exact approved catalogue is governed by the project requirements.

---

# 7. Body

`body_master` represents an actual governance body.

Conceptually:

```text
body_type_master
       │
       ▼
body_master
```

For example:

```text
Body Type:
    KENDRA_GOVERNING_BODY

Body:
    Kendra Governing Body — [Applicable Organization]
```

---

# 8. Position

`position_master` represents reusable governance positions.

Existing frozen positions include:

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

The source identifies these positions as frozen.

Additional positions may be introduced later without redesigning the entire
governance architecture.

---

# 9. Body Member Assignment

`body_member_assignment` records the association between:

```
Person / Member
Governance Body
Position
```

Conceptually:

```text
Body
  │
  ▼
body_member_assignment
  │
  ├── Person/Member
  │
  └── Position
```

---

# 10. Governance History

The unified assignment model preserves historical governance membership.

Example:

```text
2023–2026
President = A

2026–2029
President = B

2029–2032
President = C
```

These changes can be represented through assignment history rather than
creating separate history tables for every body.

The source explicitly identifies historical tracking as a benefit of the
Unified Body Governance Model.

---

# 11. Acting Positions

`acting_position_assignment` represents temporary acting responsibility.

This allows the system to distinguish:

```
Permanent / Normal Position Assignment
Acting Position Assignment
```

without replacing the underlying governance history.

---

# 12. Election Management

Election functionality forms part of the Governance Module.

The related election architecture includes:

```
election
election_nomination
election_vote
election_result
```

These support the election lifecycle.

---

# 13. Election Scope

The Governance Module may manage:

```
Election Definition
Election Nomination
Voting
Election Result
```

The detailed election business rules remain governed by the frozen
Governance/Election framework.

---

# 14. General Body

The General Body is represented as a governance concept within the overall
Governance framework.

It shall not require a completely independent governance architecture when
the unified model can represent the relevant structure.

---

# 15. Advisory Board

The Advisory Board is part of the Governance Module.

It uses the unified body architecture rather than a separate
`advisory_board_member` model.

The earlier architecture explicitly replaced the separate advisory-board
membership structure with the unified assignment model.

---

# 16. Mahila Parichalana Mandali

Mahila Parichalana Mandali is a governance body.

It is therefore represented using the unified governance architecture.

It does not require a separate governance-member table.

---

# 17. Sevak Sangha Executive

The Sevak Sangha Executive can use:

```
body_type_master
body_master
position_master
body_member_assignment
```

The Sevak module currently references the existing ERP RBAC and
organizational-scope architecture rather than creating a separate permission
system.

Detailed Sevak executive rules remain subject to the Sevak module's pending
operational decisions.

---

# 18. Future Committees

The architecture intentionally supports future committees.

A new committee can be represented as another `body_master` record with an
appropriate `body_type_master`.

No new table should be required merely because a new committee is created.

---

# 19. Governance vs Organization

Governance and Organization are separate modules.

## Organization

Owns:

```
Organizational Units
Organizational Hierarchy
Organizational Relationships
```

## Governance

Owns:

```
Governing Bodies
Positions
Assignments
Acting Assignments
Elections
Governance Structures
```

---

# 20. Governance vs Membership

Membership owns:

```
Person's Membership
Sangha Sevi ID
Membership Lifecycle
```

Governance owns:

```
Governance Body Assignment
Governance Position
Election Participation
```

Membership eligibility may be a prerequisite for a governance assignment,
but Governance does not become the owner of Membership.

---

# 21. Governance vs RBAC

Governance positions are not automatically application permissions.

For example:

```
President
Secretary
Treasurer
```

are governance positions.

Application permissions are managed by centralized RBAC.

Therefore:

```text
Governance Position
        ≠
Application Role
```

---

# 22. Governance and Authentication

Governance users authenticate through the common Authentication & Security
framework.

Governance does not create its own login system.

---

# 23. Governance and Authorization

Governance operations use:

```
Central RBAC
+
Organizational Scope
```

A governance position shall not automatically become an application
permission unless explicitly mapped through approved authorization rules.

---

# 24. Governance and Audit

Governance changes require auditability.

Examples include:

```
Body Creation
Position Assignment
Position Change
Acting Assignment
Election Creation
Nomination
Result Recording
```

The common Audit framework remains authoritative.

---

# 25. Historical Integrity

Governance history shall be preserved.

The system shall not overwrite historical assignments in a way that destroys
the ability to determine who held a position during a previous period.

---

# 26. Statutory Authority

Governance structures represented in the ERP must remain aligned with the
authoritative NSS Bye-Law.

The Constitution remains the highest governing authority.

Project governance documentation cannot override statutory authority.

---

# 27. Governance Decision Authority

Changes to the project's governance architecture must follow the approved
Governance Decision Register process.

The GDR is the authoritative repository for approved governance decisions.

---

# 28. Governance Bodies Are Data

A governance body is represented as data rather than hard-coded application
logic.

This allows:

```
New Bodies
Future Committees
Different Organizational Scopes
Historical Bodies
```

to be represented without structural redesign.

---

# 29. Positions Are Reusable

A position is represented through `position_master`.

The same position may be applicable to multiple governance bodies where the
governance rules permit it.

Example:

```text
PRESIDENT
   │
   ├── Kendra Governing Body
   ├── Sakha Governing Body
   └── Other Approved Bodies
```

---

# 30. Assignment Is Historical

A governance assignment represents an actual person/member occupying a
position within a body.

Assignments must preserve relevant effective periods/history.

---

# 31. Acting Assignment

Acting appointments must be distinguishable from normal assignments.

Example:

```text
Secretary
   │
   └── Acting Secretary → Person B
```

while preserving the underlying governance position.

---

# 32. Election Result

Election results shall not simply overwrite the previous office holder.

The resulting assignment shall create a new governance state while
preserving previous history.

---

# 33. Election and Assignment

The logical relationship is:

```text
Election
   ↓
Election Result
   ↓
Governance Assignment
```

The exact physical workflow is defined in the Election/Business Rules
documentation.

---

# 34. Governance Body Expansion

The Unified Body Governance Model intentionally supports expansion without
schema redesign.

For example:

```text
body_type_master
        │
        ├── KENDRA_GOVERNING_BODY
        ├── SAKHA_GOVERNING_BODY
        ├── ADVISORY_BOARD
        ├── MAHILA_PARICHALANA_MANDALI
        ├── SEVAK_SANGHA_EXECUTIVE
        └── UPBS_COMMITTEE
```

---

# 35. No Body-Specific Member Tables

The architecture shall not create:

```
governing_body_member
advisory_board_member
mahila_member
sevak_member
committee_member
```

as separate governance membership structures.

The unified:

```
body_member_assignment
```

model is authoritative.

This consolidation is explicitly frozen.

---

# 36. No Body-Specific Position Tables

The architecture shall not create separate:

```
governing_body_position
advisory_board_position
committee_position
```

tables.

`position_master` provides the reusable position definition.

---

# 37. Governance Scope

A governance body is associated with the appropriate organizational context.

Examples:

```
Kendra Governing Body → Kendra
Sakha Governing Body → Sakha
Advisory Board → Approved Governance Scope
Mahila Parichalana Mandali → Applicable Scope
```

The exact organization FK relationships are defined in ERD/Table Design.

---

# 38. Governance Lifecycle

A governance body may conceptually progress through:

```text
Created
   ↓
Active
   ↓
Reconstituted / Superseded
   ↓
Historical
```

Exact status values require final business-rule confirmation where not
already frozen.

---

# 39. Governance Position Lifecycle

A position assignment may conceptually progress through:

```text
Assigned
   ↓
Active
   ↓
Ended
   ↓
Historical
```

Acting assignments follow a separate temporary assignment lifecycle.

---

# 40. Governance History

The system must preserve:

```
Who
Held Which Position
In Which Body
During Which Period
```

where the governance rules require that information.

---

# 41. Future-Proof Architecture

The unified architecture is intentionally designed to support future
governance bodies without schema redesign.

This is one of the principal architectural benefits of the Governance
Module.

---

# 42. Core Governance Tables

The current unified governance foundation consists of:

```text
body_type_master
position_master

body_master
body_member_assignment
acting_position_assignment
```

The source explicitly identifies these as the current core governance
tables.

---

# 43. Related Election Tables

Election functionality additionally uses:

```text
election
election_nomination
election_vote
election_result
```

These are related Governance entities rather than replacements for the
unified body model.

---

# 44. Governance Module Structure

```text
Governance
│
├── Body Types
│   └── body_type_master
│
├── Bodies
│   └── body_master
│
├── Positions
│   └── position_master
│
├── Assignments
│   ├── body_member_assignment
│   └── acting_position_assignment
│
└── Elections
    ├── election
    ├── election_nomination
    ├── election_vote
    └── election_result
```

---

# 45. Design Principle

The central Governance architecture is:

```text
Body Type
    ↓
Body
    ↓
Position
    ↓
Member Assignment
    ↓
Historical Governance State
```

with:

```text
Election
    ↓
Election Result
    ↓
New Assignment
```

---

# 46. No Functional UI Design Yet

This document does not define functional screen designs.

Governance UI will be addressed separately after:

```
Overview
ERD
Business Rules
Table Design
```

are completed.

---

# 47. No API Design Yet

This document does not define REST/API contracts.

API design will follow the project's:

```
Database First
API First
UI
```

implementation sequence after the schema/documentation baseline is
complete.

---

# 48. No SQL Yet

No PostgreSQL DDL is defined by this document.

SQL will be generated only after the Governance table design is finalized
and the broader schema baseline is ready.

---

# 49. Current Governance Status

The source identifies the following as frozen:

```
Governance Framework
Unified Body Governance Model
Advisory Board
General Body
Election Framework
Vacancy Framework
Mahila Parichalana Mandali
```

The unified governance architecture itself is therefore treated as frozen.

---

# 50. Important Pending Boundary

Although the Governance architecture is frozen, this document does not
invent detailed rules where the source does not provide them.

Examples requiring their own detailed documentation/confirmation include:

```
Election operational workflow details
Exact term-duration rules where applicable
Detailed nomination rules
Detailed voting rules
Exact vacancy workflow
Detailed acting-position rules
```

These belong to the Governance Business Rules/ERD/Table Design sequence.

---

# 51. Source Alignment

The Project Module Division identifies Governance as a dedicated module
covering:

```
General Body
Governing Body
Advisory Board
Mahila Parichalana Mandali
Committees
Position Assignment
Election Management
```

and identifies the unified governance core.

The Unified Body Governance Model explicitly replaces body-specific member
tables with:

```
body_master
body_member_assignment
position_master
body_type_master
acting_position_assignment
```

and supports historical governance assignments and future committees without
schema changes.

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
