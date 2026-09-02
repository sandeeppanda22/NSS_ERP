# NSS ERP Governance Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0/v0.1.0 (lifecycle doc). Full Solution design now 5 files;
`backend/governance/` remains a pure Django app stub (empty `models.py`/`views.py`, no
`urls.py`, not in `INSTALLED_APPS`).

**Not to be confused with `docs/00_Project_Governance/`**, which governs the *project itself*
(AUTH/GOV/GDR/STD documents, the Governance Baseline) — this folder is the ERP *business
domain* module for the Sangha's own governing bodies. Same word, two different layers.

---

## Documents

01_governance_module_overview.md (`SOL-GOV-001`) — Version 1.0.0
Purpose: Unified architecture for Governing Bodies, General Body, Advisory Board, Mahila
Parichalana Mandali, Committees, Position Assignment, Acting Positions, and Elections.

02_governance_erd.md — Version 1.0.0
Purpose: Entity relationship design for the Unified Body Governance Model + Election entities.

03_governance_lifecycle.md — Version 0.1.0, DRAFT, Document ID `SOL-GOV-005`
Purpose: `body_master` states (CREATED/ACTIVE/RECONSTITUTED/HISTORICAL), `position_master`,
`body_member_assignment`/`acting_position_assignment` (ACTIVE/ENDED), election lifecycle
(PLANNED→…→COMPLETED/CANCELLED), Mahila selection+election, vacancy lifecycle, Person-death
cascade effects.

04_governance_business_rules.md — Version 1.0.0, GOV-BR-001–GOV-BR-093 (was `03_...` before
the lifecycle doc was inserted and file numbers shifted down one slot)
Purpose: Business rules for the frozen position set, election process, and Mahila Parichalana
Mandali composition.

05_governance_table_design.md — Version 1.0.0 (was `04_...`)
Purpose: Physical table design — nine tables.

---

## Key facts

- **Unified Body Governance Model (frozen):** `body_type_master`, `body_master`,
  `position_master`, `body_member_assignment`, `acting_position_assignment` — supersedes older
  body-specific tables (`governing_body_member`, `advisory_board_member`, `mahila_member`,
  `sevak_member`, `committee_member`), none of which are frozen anymore.
- **Election entities:** `election`, `election_nomination`, `election_vote`, `election_result`.
- Nine tables total.
- Frozen positions: `PRESIDENT`, `VICE_PRESIDENT`, `PARICHALAK`, `SECRETARY`,
  `ASSISTANT_SECRETARY`, `TREASURER`, `MUKHYA_PUJAKA`, `MEMBER`.
- Mahila Parichalana Mandali modeled here as 9 members, 3-year term, female eligibility,
  Selection+Election, one-member-one-vote, dual office holding permitted — cross-check against
  the Mahila module's own v2.1.0 correction (`docs/03_Solution/modules/mahila/`, 9 members,
  **2-year** term) before treating either term length as settled; the two module docs
  currently disagree and this has not been reconciled (see `docs/PROJECT_DOCUMENTATION.md` →
  "Open questions / TODOs"). The new
  `03_governance_lifecycle.md` (SOL-GOV-005) restates the same 3-year figure (GOV-BR-036 in its
  own numbering) and models Mahila reconstitution via a formal consensus→election→
  `election`/`election_result` table path — `mahila/03_mahila_lifecycle.md` instead describes
  routine reconstitution as Parichalak consensus + President's consent with no formal election
  tables, reserving actual elections for President/Vice-President vacancies only. Both the term
  length AND the process model disagree between the two modules; neither is reconciled.
- **Governance Position ≠ Application Role** and geographic hierarchy ≠ organizational
  hierarchy are both explicit, frozen boundaries.

## Cross-reference gap

`03_governance_lifecycle.md` does not cite `docs/03_Solution/standards/lifecycle/
PARTICIPATION_LIFECYCLE_RULES.md` (SOL-LIFE-001) or `PERSON_LIFECYCLE_RULES.md` (SOL-LIFE-002)
even though it restates near-identical Person-death-cascade language (§36) — SOL-LIFE-001 §16
says modules "shall reference this standard rather than duplicating these rules." Not fixed
here; same gap exists in five other new lifecycle docs (person, family, attendance,
authentication, administration) — see `docs/PROJECT_DOCUMENTATION.md` → "Open questions / TODOs".

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented (SOL-GOV-005, cross-reference gap above)
· Business Rules Drafted (SOURCE ALIGNED) · Table Design
Drafted (SOURCE ALIGNED) · SQL Implementation Not Started · `backend/governance/` remains an
empty stub, not in `INSTALLED_APPS`
