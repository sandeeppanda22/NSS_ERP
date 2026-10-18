# database/ddl/08_governance/

Governance Module DDL — 10 tables implementing the **Unified Body Governance Model**
(Tier 6). **DRAFT / in-progress** (vertical slice: Business Rules → Documentation →
**DDL (this folder)** → API → UI → Tests).

Authority: SOL-GOV-002 (ERD), SOL-GOV-003 (Business Rules `GOV-BR-001`…`GOV-BR-093`),
SOL-GOV-004 (Table Design), and `docs/03_Solution/architecture/DDL_CREATION_ORDER.md`
(SOL-ARCH-010, FROZEN).

## DDL Execution Order

Execute AFTER Authentication (`06_authentication/`) and Administration (`07_administration/`),
and after the foundational `organization`, `person`, and `sangha_sevi` tables already exist
(earlier phases). Within this module the two Depth-0 masters come first, then `body_master`,
then the assignment tables, then the election chain. The `#` column is the global order from
`DDL_CREATION_ORDER.md`; the Depth column is the global FK depth.

| File | Table | Global # | Depth | Depends on |
|------|-------|---------:|------:|------------|
| `01_body_type_master.sql` | `body_type_master` | 11 | 0 | — |
| `02_position_master.sql` | `position_master` | 12 | 0 | — |
| `03_body_master.sql` | `body_master` | 38 | 4 | `body_type_master`, `organization` |
| `04_body_member_assignment.sql` | `body_member_assignment` | 62 | 5 | `body_master`, `position_master`, `person`, `sangha_sevi` |
| `05_acting_position_assignment.sql` | `acting_position_assignment` | 63 | 5 | `body_master`, `position_master`, `person` |
| `06_election.sql` | `election` | 64 | 5 | `body_master`, `organization` |
| `07_election_nomination.sql` | `election_nomination` | 73 | 6 | `election`, `position_master`, `person` |
| `08_election_vote.sql` | `election_vote` | 74 | 6 | `election`, `election_nomination`, `position_master`, `person` |
| `09_election_result.sql` | `election_result` | 75 | 6 | `election`, `election_nomination`, `position_master`, `person` |
| `10_election_vote_participation.sql` | `election_vote_participation` | — (added in Tier 6; not in the frozen sequence) | 6 | `election`, `position_master`, `person` |

> **Ballot immutability.** `11_governance_immutability.sql` adds a function + `BEFORE UPDATE`
> triggers on `election_vote` and `election_vote_participation` — not a table, run via `run_sql`
> (idempotent `CREATE OR REPLACE` / `DROP..CREATE TRIGGER`), not `run_ddl`.

> **Wiring status.** Created by **Phase 11b** in `database/scripts/02_build.sh`,
> `database/scripts/02_build.ps1`, and `render_build.sh` (after Administration, before the
> `nss_db_writer` grant — so Phase 12 `GRANT ON ALL TABLES` and the Phase 14 audit trigger
> cover these tables). Existence-validated by the Governance block in
> `database/scripts/03_validate.sh` / `.ps1`. The grant scripts need no edit — they use
> `ALTER DEFAULT PRIVILEGES` + `ON ALL TABLES`, so these tables are covered automatically.
> `FK_DEPENDENCY_GRAPH.md` (SOL-ARCH-009, frozen) lists these tables. **Seed folder:**
> `database/seed/08_governance/` seeds the two Depth-0 catalogues (`body_type_master`,
> `position_master`) with the owner-confirmed starter codes (2026-10-07) plus the 3 NSS-wide singleton `body_master` rows — run as Phase 11c in
> `02_build.sh`/`.ps1`/`render_build.sh`, right after Phase 11b's DDL and before the Phase 12
> writer grant. Both catalogues remain caller-extensible via the Governance API
> (`POST`/`PATCH /body-types`, `/positions`) for anything the starter seed doesn't cover.
>
> **2026-10-09 follow-on (§63 composite auto-grant rule):** `body_type_master` gained 3 more
> org-scoped governance body types — `ANCHALIKA_GOVERNING_BODY`, `ZILLA_GOVERNING_BODY`,
> `PATHA_CHAKRA_GOVERNING_BODY` (same admin-created-per-organization-instance pattern as
> `SAKHA_GOVERNING_BODY`; see `database/seed/08_governance/01_body_type_master.sql` v1.1).
> These additions matter beyond data modeling: `body_type_master` rows are now RBAC-significant
> — `api/services/rbac_service.py`'s `load_user_context()` / `load_composite_grants()` reads
> body/position holdings to auto-grant the matching `NSS_ERP_*_ADMIN` role (e.g. holding the
> President/Secretary position on one of these bodies auto-grants the corresponding
> organizational admin role), so a future reader should treat new rows in this table as a
> potential RBAC surface change, not purely descriptive data. `role_master` correspondingly
> gained a 10th role, `NSS_ERP_ADVISORY_BOARD_ADMIN` (see `database/seed/00_bootstrap/02_role_master.sql`
> v1.3), and `admin_scope`'s `chk_admin_scope_org_consistency` CHECK constraint was updated to
> also exempt `KENDRA`/`KENDRA_MAHILA_SANGHA`/`ADVISORY_BOARD` scope levels (alongside `NSS-WIDE`) from requiring a non-NULL
> `organization_pk` (see `database/ddl/07_administration/02_admin_scope.sql` v1.1; `role_master.scope_level` accepts `ADVISORY_BOARD` too).

## What These Tables Are For

- **`body_type_master`** — classification master for governance bodies
  (`KENDRA_GOVERNING_BODY`, `SAKHA_GOVERNING_BODY`, `ADVISORY_BOARD`,
  `MAHILA_PARICHALANA_MANDALI`, …). Own master table (like `role_master`), not a
  `master_data` category — matches frozen DDL order #11.
- **`position_master`** — reusable governance positions (`PRESIDENT`, `VICE_PRESIDENT`,
  `PARICHALAK`, `SECRETARY`, `ASSISTANT_SECRETARY`, `TREASURER`, `MUKHYA_PUJAKA`, `MEMBER`).
  **A position is NOT an RBAC role — there is deliberately NO FK to `role_master`**
  (GOV-BR-014). Governance standing and application permission are separate domains.
- **`body_master`** — an actual governance body. `organization_pk` is nullable (NSS-wide /
  Kendra-level bodies carry NULL; org-scoped bodies carry the org). No new org structure is
  introduced (GOV-BR-058).
- **`body_member_assignment`** — the core transaction table: who (Person) holds which
  position in which body, for what term. Replaces all body-specific member tables
  (GOV-BR-004). `person_pk` is the authoritative identity; `sangha_sevi_pk` is nullable
  membership context.
- **`acting_position_assignment`** — temporary/acting occupancy of a position, kept separate
  from substantive assignments so interim cover never pollutes the standing history.
- **`election`** — an election event that reconstitutes/fills a body; carries the timeline
  (nomination/voting windows), a status lifecycle (`SCHEDULED`/`NOMINATION`/`VOTING`/`COMPLETED`/`CANCELLED`) and `is_secret_ballot` (per-election open vs secret ballot).
- **`election_nomination`** — a candidate nominated for one position in an election
  (optional recorded proposer).
- **`election_vote`** — one ballot cast FOR a nomination at a position. `voter_person_pk` is
  nullable: populated for an open ballot, NULL for a secret one. Append-only (see below).
- **`election_vote_participation`** — the voter ledger: one row per (election, position, voter)
  recording THAT a member voted, never WHICH candidate; the authoritative
  one-member-one-vote-per-position gate in both ballot modes. Append-only.
- **`election_result`** — the decided outcome for one position (winner / uncontested / tie /
  vacant). Declaring a result does NOT itself write `body_member_assignment` — that hand-off
  is a downstream business/API step.

## Design Decisions Carried in This Pass (for review)

Each `.sql` file has a `-- Design decisions:` header block. The notable ones:

1. **Status vocabularies use `VARCHAR + CHECK`**, not a `master_data` FK — consistent with
   `user_account.account_status` / `approval_status`, and avoids inventing new `master_data`
   category values ahead of seed governance. Finalized at DDL per the relevant `GOV-BR`
   lifecycle rules (the design docs explicitly deferred physical status codes to this phase).
   `body_member_assignment.assignment_status` gained a fifth value, `PENDING_REMOVAL`, on
   2026-10-08: a forced removal of a Sakha-nominated seat (e.g. Advisory Board), initiated via
   NSS-admin break-glass, parks here until the body's own sitting President approves (→ `ENDED`)
   or rejects (→ `ACTIVE`) it. The Sakha's own direct self-withdrawal never passes through this
   state — it remains instant, as owner-confirmed earlier the same day.
2. **`organization_pk` nullable** on `body_master` and `election` (NSS-wide vs org-scoped).
3. **`person_pk` is the authoritative identity** everywhere a human is referenced; no duplicate
   Person is created in Governance (GOV-BR-057/074). On `body_member_assignment`,
   `sangha_sevi_pk` is **NOT NULL** — a governance office-holder must be an active NSS member,
   and the API validates the Sangha Sevi is active and belongs to `person_pk` (GOV-BR-056/074).
4. **Occupancy is NOT hard-capped at the DB.** The partial unique indexes only stop the *same*
   person holding the *same* position in the *same* body in two concurrently-active rows. Seat
   limits (e.g. single-holder President vs multi-holder MEMBER) are business/API composition
   rules (SOL-GOV-004 §25/§8.9).

## Vote Secrecy and Ballot Immutability (RESOLVED 2026-10-09)

The earlier open item (GOV-BR-045 / SOL-GOV-004 §12.6: ballots attributable to the voter) is
resolved by a per-election switch, `election.is_secret_ballot`. `election_vote.voter_person_pk`
is **nullable**: populated for an OPEN ballot, NULL for a SECRET one. Eligibility and
one-vote-per-position are enforced in both modes by the separate
`election_vote_participation` ledger, which carries no link to the chosen nomination, so a
secret choice can never be joined back to its voter. `election_vote` and
`election_vote_participation` rows are immutable: `11_governance_immutability.sql` rejects any
UPDATE (`nss.fn_block_update()`); the only way to clear them is the reset flow, which
hard-DELETEs them (audit-logged).

## Audit Columns

Standard block on every table: `created_at`, `created_by_sangha_sevi_pk` (nullable),
`updated_at`, `updated_by_sangha_sevi_pk`, `deleted_at`, `deleted_by_sangha_sevi_pk`,
`is_active`. Audit-actor FKs (`*_by_sangha_sevi_pk`) are nullable columns in this pass — their
FK constraints are deferred to Pass 2, same as every other module. Soft-delete is enforced by
`chk_*_soft_delete` on each table.
