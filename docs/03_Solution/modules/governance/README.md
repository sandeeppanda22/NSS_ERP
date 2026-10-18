# NSS ERP Governance Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0/v0.1.0 (lifecycle doc). Full Solution design now 5 files.
**Tier 6 implementation is in progress (uncommitted on `feature/tier6-governance`)**:
`database/ddl/08_governance/` (10 tables), `database/seed/08_governance/`, `api/routers/governance.py`
(46 endpoints), `api/schemas/governance.py`, `tests/api/test_governance.py`. The design docs below
have not all been reconciled to it (see "Implementation drift"). (The Django prototype, which never had more than an empty
`governance` app stub, was removed from the repository entirely — see
`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md`).

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
Purpose: Physical table design — nine tables (the implemented DDL has ten; see "Implementation drift").

---

## Key facts

- **Unified Body Governance Model (frozen):** `body_type_master`, `body_master`,
  `position_master`, `body_member_assignment`, `acting_position_assignment` — supersedes older
  body-specific tables (`governing_body_member`, `advisory_board_member`, `mahila_member`,
  `sevak_member`, `committee_member`), none of which are frozen anymore.
- **Election entities:** `election`, `election_nomination`, `election_vote`, `election_result`.
- Nine tables in the design; **ten in the implemented DDL** (adds `election_vote_participation`).
- Frozen positions: `PRESIDENT`, `VICE_PRESIDENT`, `PARICHALAK`, `SECRETARY`,
  `ASSISTANT_SECRETARY`, `TREASURER`, `MUKHYA_PUJAKA`, `MEMBER` (the implemented seed adds
  `JOINT_SECRETARY` and `CASHIER` — 10 positions).
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

## Implementation drift (design docs vs. Tier 6 code)

Recorded here, not redesigned. The design docs are unchanged; the implementation differs as follows:

- **Tables:** 10 implemented vs 9 designed — `election_vote_participation` (voter ledger) was
  added for the secret-ballot resolution (2026-10-09).
- **Vote secrecy / immutability:** `election.is_secret_ballot` and a nullable
  `election_vote.voter_person_pk` realise the GOV-BR-045 secrecy resolution; ballots and
  participation rows are append-only via `nss.fn_block_update()` triggers
  (`11_governance_immutability.sql`); reset hard-DELETEs them.
- **Status vocabularies** are `VARCHAR + CHECK`, finalized at DDL: `election_status` is
  `SCHEDULED`/`NOMINATION`/`VOTING`/`COMPLETED`/`CANCELLED` (the lifecycle doc's PLANNED/COUNTING
  names do not exist in the DDL); `body_member_assignment.assignment_status` is
  `ASSIGNED`/`ACTIVE`/`ENDED`/`HISTORICAL`/`PENDING_REMOVAL`.
- **Positions:** seed has 10 (adds `JOINT_SECRETARY`, `CASHIER`); body types: 8 (adds
  `SEVAK_SANGHA_EXECUTIVE` and the Anchalika/Zilla/Patha Chakra governing bodies).
- **RBAC:** `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE` permissions and the
  `NSS_ERP_ADVISORY_BOARD_ADMIN` role (auto-granted from body/position holdings by
  `rbac_service.load_composite_grants`; `ADVISORY_BOARD` admin-scope level).
- `database/ddl/08_governance/README.md` is the code-verified reference for the DDL.

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
Drafted (SOURCE ALIGNED) · SQL + API implementation in progress (Tier 6, uncommitted) · UI/tests per `tests/README.md`
