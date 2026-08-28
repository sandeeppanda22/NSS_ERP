# NSS ERP — Governance Business Rules

**Document ID:** SOL-GOV-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Governance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing NSS ERP's Governance
Module.

The rules cover:

    Governing Bodies
    General Body
    Advisory Board
    Unified Body Governance
    Position Assignment
    Acting Positions
    Elections
    Vacancies
    Mahila Parichalana Mandali
    Governance History

---

# 2. Governance Authority

## GOV-BR-001 — By-Law Supremacy

**Status:** FROZEN

The NSS Bye-Law and approved amendments/resolutions have precedence over
software design.

Where software behaviour conflicts with an authoritative governing source,
the authoritative source prevails.

The project's source hierarchy explicitly establishes the Bye-Law as the
highest authority.

---

## GOV-BR-002 — Governance Decision Control

**Status:** FROZEN

Governance changes affecting the project architecture shall follow the
approved Governance Decision Register and change-control process.

The Governance Decision Register is the authoritative record of approved
governance decisions.

---

# 3. Unified Governance Model

## GOV-BR-003 — Unified Body Governance Model

**Status:** FROZEN

All supported governance bodies shall use the unified governance model.

Core entities:

    body_type_master
    body_master
    position_master
    body_member_assignment
    acting_position_assignment

This model replaces separate body-specific membership structures.

---

## GOV-BR-004 — No Body-Specific Governance Membership Tables

**Status:** FROZEN

The system shall not create separate governance-member tables such as:

    governing_body_member
    advisory_board_member
    mahila_member
    sevak_member
    committee_member

The unified:

    body_member_assignment

model is authoritative.

---

## GOV-BR-005 — Future Bodies Use Existing Model

**Status:** FROZEN

A new governance body shall normally be represented through:

    body_type_master
    body_master
    position_master
    body_member_assignment

without schema redesign.

Examples include future:

    UPBS Committees
    Publication Committee
    Finance Committee
    Disciplinary Committee
    Special Task Force

The source explicitly identifies this future-expansion capability.

---

# 4. Governance Body

## GOV-BR-006 — Body Type Classification

**Status:** FROZEN

Every governance body shall have an applicable body type.

The body type identifies the category of governance body.

---

## GOV-BR-007 — Body Identity

**Status:** SOURCE-ALIGNED

Each actual governance body shall have its own persistent identity.

The body identity shall not be recreated for every assignment or election.

---

## GOV-BR-008 — Body Scope

**Status:** SOURCE-ALIGNED

A governance body shall operate within its applicable organizational or
governance scope.

The exact physical relationship with Organization is defined during Table
Design.

---

# 5. Governing Body

## GOV-BR-009 — Kendra Governing Body

**Status:** FROZEN

The Kendra Sangha has a Governing Body as established by the Bye-Law.

The Bye-Law identifies a nine-member structure.

---

## GOV-BR-010 — Kendra Governing Body Positions

**Status:** FROZEN

The identified positions are:

    President
    Vice-President
    Parichalak
    Secretary
    Assistant Secretary
    Treasurer
    Members

The source explicitly identifies these office-bearer positions.

---

## GOV-BR-011 — Nine-Member Structure

**Status:** FROZEN

The Kendra Governing Body shall consist of the statutorily defined
nine-member structure.

The database must not permit governance assignments that silently violate
the applicable body composition rules.

---

# 6. Position Management

## GOV-BR-012 — Position Master

**Status:** FROZEN

Governance positions shall be represented through:

    position_master

rather than separate position tables for individual bodies.

---

## GOV-BR-013 — Position Reuse

**Status:** FROZEN

A position definition may be used by multiple governance bodies where the
governance rules permit it.

---

## GOV-BR-014 — Position Does Not Equal Application Role

**Status:** FROZEN

A governance position is not automatically an application RBAC role.

Therefore:

    President
    Secretary
    Treasurer

do not automatically mean:

    ROLE_ADMIN
    ROLE_APPROVER
    ROLE_MANAGER

Application authorization remains under Administration/RBAC.

---

# 7. Governance Assignment

## GOV-BR-015 — Assignment Identity

**Status:** FROZEN

A governance assignment identifies:

    Person/Member
    Governance Body
    Governance Position
    Applicable Assignment Period

where applicable.

---

## GOV-BR-016 — Assignment History

**Status:** FROZEN

Governance assignments shall preserve historical information.

The system shall be able to determine who held a position in a body during
the relevant historical period.

The Unified Body Governance Model explicitly supports this history.

---

## GOV-BR-017 — No Historical Overwrite

**Status:** FROZEN

A new office holder shall not overwrite the historical identity of a
previous office holder.

Example:

    2023–2026 → Person A
    2026–2029 → Person B

Both assignments remain historically available.

---

# 8. Acting Positions

## GOV-BR-018 — Acting Assignment

**Status:** FROZEN

Temporary acting responsibility shall be represented separately through:

    acting_position_assignment

---

## GOV-BR-019 — Acting Does Not Erase Normal Assignment

**Status:** FROZEN

An acting assignment shall not destroy or overwrite the underlying normal
governance assignment.

---

## GOV-BR-020 — Acting Period

**Status:** SOURCE-ALIGNED

An acting assignment shall have an identifiable effective period.

Exact date/time requirements are finalized in Table Design.

---

# 9. General Body

## GOV-BR-021 — General Body

**Status:** FROZEN

The General Body is a formal governance component of the Kendra Sangha.

The Bye-Law establishes:

    General Body
    Annual Session
    Resolution Submission Mechanism

as governance functions.

---

## GOV-BR-022 — General Body Governance

**Status:** SOURCE-ALIGNED

General Body functions shall remain within the Governance Module.

They shall not be modeled as ordinary membership transactions.

---

# 10. Advisory Board

## GOV-BR-023 — Advisory Board Exists

**Status:** FROZEN

The Kendra Sangha has an Advisory Board.

The Bye-Law identifies the Advisory Board as part of the Kendra governance
structure.

---

## GOV-BR-024 — Advisory Representation

**Status:** FROZEN

The Bye-Law identifies one representative from each Sakha Sangha as part of
the Advisory Board structure.

---

## GOV-BR-025 — Advisory Role

**Status:** FROZEN

The Advisory Board provides an advisory function to the Governing Body.

---

## GOV-BR-026 — Unified Advisory Representation

**Status:** FROZEN

Advisory Board membership shall use the unified governance assignment model.

No separate:

    advisory_board_member

architecture shall be created.

---

# 11. Mahila Sangha Governance

## GOV-BR-027 — Mahila Sangha Is an NSS Institution

**Status:** FROZEN

Mahila Sangha is an official institution within NSS.

It is not a separate independent membership system.

---

## GOV-BR-028 — Same Membership Framework

**Status:** FROZEN

Mahila Sangha members use the same NSS membership framework.

There is:

    No separate membership category
    No separate renewal process

A female member remains under the ordinary NSS membership lifecycle.

---

# 12. Mahila Parichalana Mandali

## GOV-BR-029 — Mahila Parichalana Mandali Exists

**Status:** FROZEN

Mahila Parichalana Mandali is a central supervisory governance body of
Mahila Sangha.

It provides guidance, coordination and supervision of Mahila Sangha
activities and branch Sanghas.

---

## GOV-BR-030 — Mahila Body Uses Unified Governance

**Status:** FROZEN

Mahila Parichalana Mandali shall use the Unified Body Governance Model.

No separate Mahila governance-member schema shall be created.

---

## GOV-BR-031 — Mahila Parichalana Mandali Size

**Status:** FROZEN

The currently frozen project rule defines:

    9 Members

for the Mahila Parichalana Mandali.

---

## GOV-BR-032 — Mahila Positions

**Status:** FROZEN

The nine-member structure consists of:

    President
    Vice President
    Secretary
    Assistant Secretary
    Treasurer
    Members

---

## GOV-BR-033 — Mahila Eligibility

**Status:** FROZEN

Only eligible female members may participate as candidates/voters within
the Mahila governance structure.

---

## GOV-BR-034 — Mahila Voting

**Status:** FROZEN

The voting principle is:

    One Member
        ↓
    One Vote
        ↓
    One Candidate

Only eligible female members vote.

---

## GOV-BR-035 — Mahila Selection/Election

**Status:** FROZEN

The currently frozen model is:

    Selection + Election
    Consensus First
    Election When Required

---

## GOV-BR-036 — Mahila Term

**Status:** FROZEN

The currently frozen term is:

    3 Years

---

## GOV-BR-037 — Mahila Dual Office Holding

**Status:** FROZEN

A female member may simultaneously serve on:

    Main Governing Body
    Mahila Parichalana Mandali

if elected/selected to both.

---

# 13. Elections

## GOV-BR-038 — Election Is Governance Function

**Status:** FROZEN

Election management belongs to Governance.

---

## GOV-BR-039 — Election Lifecycle

**Status:** SOURCE-ALIGNED

The election architecture supports:

    Election
    Nomination
    Voting
    Result

Conceptually:

    election
       ↓
    nomination
       ↓
    vote
       ↓
    result

---

## GOV-BR-040 — Election History

**Status:** FROZEN

Election records must preserve historical election information.

An election result shall not destroy the underlying election history.

---

## GOV-BR-041 — Election Result and Assignment

**Status:** SOURCE-ALIGNED

An election result may lead to a new governance assignment.

The resulting assignment shall preserve the historical transition.

---

# 14. Selection and Election

## GOV-BR-042 — Consensus Before Election

**Status:** FROZEN

Where the applicable governance rules follow the Selection + Election
model, consensus/selection should be attempted first.

Election occurs when required.

This principle is explicitly used for Mahila Parichalana Mandali and aligned
with the broader governance framework.

---

# 15. Voting

## GOV-BR-043 — Voting Eligibility

**Status:** SOURCE-ALIGNED

Only persons satisfying the applicable governance/election eligibility rules
may vote.

---

## GOV-BR-044 — One Member One Vote

**Status:** FROZEN where applicable

Where the applicable election rule uses the standard one-member-one-vote
model:

    One eligible member
          =
    One vote

---

## GOV-BR-045 — Vote Integrity

**Status:** SOURCE-ALIGNED

The system shall preserve the integrity of recorded votes.

The exact privacy/secrecy implementation is not frozen by this document.

---

# 16. Election Nomination

## GOV-BR-046 — Candidate Nomination

**Status:** SOURCE-ALIGNED

Candidates shall be represented through election nominations before being
included in the election result.

---

## GOV-BR-047 — Eligibility Before Nomination

**Status:** SOURCE-ALIGNED

Candidate eligibility shall be checked according to the applicable
governance rules before the candidate participates in the election.

---

# 17. Election Result

## GOV-BR-048 — Result Is Historical

**Status:** FROZEN

An election result shall remain available as historical governance
information.

---

## GOV-BR-049 — Result Does Not Overwrite History

**Status:** FROZEN

Recording a new election result shall not overwrite previous election
results or previous governance assignments.

---

# 18. Vacancy

## GOV-BR-050 — Vacancy Framework

**Status:** FROZEN

Vacancy management is part of the Governance Module.

The project baseline identifies the Vacancy Framework as frozen.

---

## GOV-BR-051 — Vacancy Preserves History

**Status:** FROZEN

When a position becomes vacant, the previous holder's historical assignment
must remain preserved.

---

## GOV-BR-052 — Vacancy Does Not Delete Position

**Status:** SOURCE-ALIGNED

A vacant office remains a valid governance position even when no person is
currently assigned.

---

## GOV-BR-053 — Vacancy Filling

**Status:** SOURCE-ALIGNED

A vacancy may be filled through the applicable approved governance
selection/election/appointment mechanism.

The exact mechanism depends on the governing rules applicable to the body.

---

# 19. Governance Terms

## GOV-BR-054 — Term-Based Governance

**Status:** FROZEN where applicable

Governance assignments may operate over defined terms.

For Mahila Parichalana Mandali, the frozen term is three years.

The exact term for each other body must follow its authoritative governance
rule and shall not be invented by software design.

---

# 20. Membership Dependency

## GOV-BR-055 — Governance Does Not Create Membership

**Status:** FROZEN

Governance does not create or modify the core NSS membership record.

Membership remains the authoritative domain.

---

## GOV-BR-056 — Governance Eligibility

**Status:** SOURCE-ALIGNED

Where membership status is an eligibility condition, Governance shall
validate against the authoritative Membership module.

---

# 21. Person Dependency

## GOV-BR-057 — Person Identity

**Status:** FROZEN

Governance shall use the authoritative Person identity.

No duplicate Person record shall be created for governance participation.

---

# 22. Organization Dependency

## GOV-BR-058 — Organization Ownership

**Status:** FROZEN

Organization owns organizational structure.

Governance owns governance bodies and assignments.

---

## GOV-BR-059 — Governance Scope

**Status:** SOURCE-ALIGNED

A governance body shall be associated with its applicable organizational
scope.

---

# 23. RBAC

## GOV-BR-060 — Central RBAC

**Status:** FROZEN

Governance shall use the centralized ERP RBAC framework.

It shall not create a separate Governance permission architecture.

---

## GOV-BR-061 — Position Does Not Grant Permission

**Status:** FROZEN

Holding:

    President
    Secretary
    Treasurer
    Parichalak

does not automatically grant application permissions.

Permissions are determined by the centralized RBAC model.

---

# 24. Audit

## GOV-BR-062 — Governance Changes Audited

**Status:** FROZEN

Governance changes shall be auditable.

Examples:

    Body Creation
    Assignment
    Assignment End
    Acting Assignment
    Election
    Nomination
    Result
    Vacancy
    Governance Configuration Change

---

## GOV-BR-063 — Historical Preservation

**Status:** FROZEN

Governance history shall not be physically deleted merely to remove it from
current operational views.

---

# 25. Statutory Change

## GOV-BR-064 — Statutory Authority

**Status:** FROZEN

Software shall not independently introduce governance structures that
conflict with the Bye-Law or approved amendments.

---

## GOV-BR-065 — Governance Change Traceability

**Status:** FROZEN

Governance changes shall remain traceable to the applicable authoritative
reference, governance decision, or approved project rule.

The project traceability standard requires bidirectional traceability across
REF → REQ → SOL → implementation → TEST → RELEASE.

---

# 26. Historical Governance

## GOV-BR-066 — History Never Deleted

**Status:** FROZEN

Governance history follows the project-wide:

    History Never Deleted

principle.

---

## GOV-BR-067 — Historical Position Holder

**Status:** FROZEN

The system must be able to determine historical office holders.

---

## GOV-BR-068 — Historical Body

**Status:** SOURCE-ALIGNED

A body that is no longer active may remain historically available.

---

# 27. Unified Architecture Rules

## GOV-BR-069 — No Duplicate Body Logic

**Status:** FROZEN

Business logic shall not be duplicated merely because two governance bodies
have similar structures.

---

## GOV-BR-070 — Body Type Controls Behaviour

**Status:** SOURCE-ALIGNED

Where governance rules differ by body type, the applicable body type shall
determine the relevant rules.

---

## GOV-BR-071 — Domain-Specific Rules Remain Explicit

**Status:** FROZEN

A unified database structure does not imply that every governance body has
identical business rules.

For example:

    Kendra Governing Body
    Advisory Board
    Mahila Parichalana Mandali

may have different eligibility, composition or selection rules while still
using the same underlying schema.

---

# 28. Data Integrity

## GOV-BR-072 — Valid Body

**Status:** FROZEN

A governance assignment must reference a valid governance body.

---

## GOV-BR-073 — Valid Position

**Status:** FROZEN

A governance assignment must reference a valid governance position.

---

## GOV-BR-074 — Valid Person

**Status:** FROZEN

A governance assignment must reference an authoritative Person/Membership
identity.

---

## GOV-BR-075 — Assignment Consistency

**Status:** SOURCE-ALIGNED

Assignment periods must not create impossible historical states.

The final database constraints are defined in Table Design.

---

# 29. Advisory Board and Governing Body Relationship

## GOV-BR-076 — Advisory Role

**Status:** FROZEN

The Advisory Board has an advisory relationship to the Governing Body.

The source identifies this relationship explicitly.

---

## GOV-BR-077 — Amendment Authority

**Status:** FROZEN

The Bye-Law identifies combined Governing Body + Advisory Board authority
for amendment of Bye-Laws, subject to the governing provisions.

Software shall represent this authority only in accordance with the
authoritative source.

---

# 30. Governance and Finance

## GOV-BR-078 — Finance Is Not Owned by Governance

**Status:** SOURCE-ALIGNED

Governance may approve or oversee financial matters where authorized by the
Bye-Law, but Finance/financial workflows remain a separate domain.

---

# 31. Governance and Audit

## GOV-BR-079 — Annual Audit Context

**Status:** FROZEN

The Bye-Law identifies annual audit by a qualified auditor.

The ERP may support audit records and reporting, but the software does not
replace the statutory audit requirement.

---

# 32. Governance and Committees

## GOV-BR-080 — Committee Support

**Status:** FROZEN

The Governance Module shall support committees/sub-committees through the
Unified Body Governance Model.

---

## GOV-BR-081 — Committee Expansion

**Status:** FROZEN

Adding an approved committee should normally require new body/master data,
not a new database schema.

---

# 33. Future Governance Bodies

## GOV-BR-082 — Schema-Neutral Expansion

**Status:** FROZEN

Future approved governance bodies shall use the existing governance
architecture wherever their business rules permit.

---

# 34. Governance Notifications

## GOV-BR-083 — Notification Is Separate

**Status:** SOURCE-ALIGNED

Governance events may trigger notifications, but notification infrastructure
is not owned by the Governance Module.

---

# 35. Governance Reporting

## GOV-BR-084 — Reporting Uses Governance History

**Status:** SOURCE-ALIGNED

Reports shall derive governance information from the authoritative Governance
records.

Examples:

    Current Office Holders
    Historical Office Holders
    Body Composition
    Election Results
    Vacancies
    Acting Positions

---

# 36. Governance Search

## GOV-BR-085 — Unified Search

**Status:** SOURCE-ALIGNED

Governance search should operate against the unified body/assignment model.

---

# 37. Governance Lifecycle

## GOV-BR-086 — Body Lifecycle

**Status:** SOURCE-ALIGNED

A governance body may move through:

    Created
    Active
    Superseded / Reconstituted
    Historical

Exact status vocabulary requires final Table Design where not already
defined by authoritative rules.

---

## GOV-BR-087 — Assignment Lifecycle

**Status:** SOURCE-ALIGNED

A normal assignment may move through:

    Assigned
    Active
    Ended
    Historical

---

## GOV-BR-088 — Acting Assignment Lifecycle

**Status:** SOURCE-ALIGNED

An acting assignment may move through:

    Assigned
    Active
    Ended
    Historical

---

# 38. Governance Tables

## GOV-BR-089 — Core Governance Tables

**Status:** FROZEN

The unified core consists of:

    body_type_master
    body_master
    position_master
    body_member_assignment
    acting_position_assignment

---

## GOV-BR-090 — Election Tables

**Status:** FROZEN

Election functionality includes:

    election
    election_nomination
    election_vote
    election_result

---

# 39. Prohibited Duplicate Structures

## GOV-BR-091 — No Duplicate Governance Schemas

**Status:** FROZEN

Do not create separate schemas for:

    Advisory Board
    Mahila Parichalana Mandali
    Committees
    Sevak Sangha Executive

where the Unified Body Governance Model can represent them.

---

# 40. Governance Source Status

## GOV-BR-092 — Frozen Governance Baseline

**Status:** FROZEN

The current project baseline identifies as fully frozen:

    Governance Framework
    Unified Body Governance Model
    Advisory Board
    General Body
    Election Framework
    Vacancy Framework
    Mahila Sangha
    Mahila Parichalana Mandali

---

# 41. Pending Operational Detail

## GOV-BR-093 — Do Not Invent Missing Rules

**Status:** FROZEN

Where the authoritative source does not define an operational detail,
software design shall not silently invent a statutory rule.

The issue must instead be:

    Documented as pending
    Resolved through approved governance process
    Or implemented as an explicitly identified administrative rule

---

# 42. Governance Rule Summary

| Area | Status |
|---|---|
| By-Law Supremacy | FROZEN |
| Unified Body Governance Model | FROZEN |
| No Body-Specific Member Tables | FROZEN |
| Future Committee Support | FROZEN |
| Kendra Governing Body | FROZEN |
| 9-Member Kendra Structure | FROZEN |
| Advisory Board | FROZEN |
| General Body | FROZEN |
| Election Framework | FROZEN |
| Vacancy Framework | FROZEN |
| Mahila Sangha | FROZEN |
| Mahila Parichalana Mandali | FROZEN |
| Mahila 9-Member Structure | FROZEN |
| Mahila 3-Year Term | FROZEN |
| Mahila Dual Office Holding | FROZEN |
| Historical Governance | FROZEN |
| Central RBAC | FROZEN |
| Central Audit | FROZEN |
| Governance Position ≠ Application Role | FROZEN |
| Exact Physical Organization FK | PENDING |
| Detailed Election Implementation | TABLE/API DESIGN |
| Vote Secrecy Implementation | PENDING |
| Exact Status Vocabulary | TABLE DESIGN |

---

# 43. Core Governance Principle

The NSS ERP Governance Module shall represent governance as:

    Body
      ↓
    Position
      ↓
    Person/Member Assignment
      ↓
    Historical Governance State

with:

    Election
      ↓
    Result
      ↓
    New Assignment

and:

    Acting Position
      ↓
    Temporary Governance Responsibility

---

# 44. Source Alignment

The Governance source explicitly identifies the Unified Body Governance Model
as the frozen governance foundation and replaces separate
body-specific membership structures with:

    body_master
    body_member_assignment
    position_master
    body_type_master
    acting_position_assignment

The source baseline identifies Governance, the Unified Body Governance Model,
Advisory Board, General Body, Election Framework, Vacancy Framework,
Mahila Sangha and Mahila Parichalana Mandali as frozen.

The Bye-Law review confirms the Kendra Governing Body, Advisory Board,
General Body and office-bearer structure as statutory governance
entities.

The frozen Mahila rules establish the nine-member structure, positions,
female eligibility, one-member-one-vote rule, Selection + Election model,
three-year term and permitted dual office holding.

---

# 45. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0

---

# End of Document
