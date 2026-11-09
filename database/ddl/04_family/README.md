# database/ddl/04_family/

Family Module DDL — 6 tables per SOL-FAM-005, SOL-FAM-003, SOL-ARCH-010, and (for `family_link`)
ERP-DECISION — Graph-based dynamic relationship model. `family_admin` (see below) and the
move-transition guard are Tier 5 additions (released in v0.11.0).

Authority: SOL-FAM-005 (Family Table Design), SOL-FAM-003, SOL-ARCH-010 (DDL Creation Order) for
the first 4 tables; `family_link` carries its own separate `ERP-DECISION` authority tag (see its
own file header) rather than SOL-FAM-005, since it implements a specific, later design decision
rather than the original Family module design; `family_admin` cites SOL-FAM-003 FAM-045..052.

## DDL Execution Order

Execute AFTER all Foundation DDL (`database/ddl/01_foundation/`), Organization DDL
(`database/ddl/02_organization/`), and Person DDL (`database/ddl/03_person/`) — `family_group`
references `organization`, and `family_relationship`/`family_head_history`/
`family_transition_history`/`family_link`/`family_admin` all reference `person`.

| # | File | Table | Depth | Sequence |
|--:|------|-------|------:|:--------:|
| 01 | `01_family_group.sql` | `family_group` | 2 | #36 |
| 02 | `02_family_relationship.sql` | `family_relationship` | 3 | #56 |
| 03 | `03_family_head_history.sql` | `family_head_history` | 3 | #57 |
| 04 | `04_family_transition_history.sql` | `family_transition_history` | 3 | #58 |
| 05 | `05_family_link.sql` | `family_link` | 3 | — |
| 06 | `06_family_admin.sql` | `family_admin` | 3 | — |
| 07 | `07_family_move_transition_guard.sql` | *(no table — `fn_family_move_requires_transition()` + constraint trigger on `family_relationship`)* | 4 | — |
| 08 | `08_family_head_history_audit_columns.sql` | *(idempotent patch, `run_sql`)* adds `updated_at`/`updated_by_sangha_sevi_pk` to `family_head_history` on databases whose existence-gated `03` predates them (`03` now declares them) | — | — |

Run as Phase 6 of `database/scripts/02_build.sh`/`.ps1` (6 tables + the guard + the `08` patch).

## The move-transition guard (`07_family_move_transition_guard.sql`)

A `DEFERRABLE INITIALLY DEFERRED` constraint trigger (`trg_family_move_requires_transition`) on
`family_relationship`, checked at COMMIT. When a `family_relationship` row is closed
(`is_current` TRUE→FALSE) and the same person ends the transaction as a current member of a
**different** family, a matching `family_transition_history` row (`old_family_group_pk` = the
family they left) must exist, otherwise the transaction fails with
`integrity_constraint_violation`. A plain removal (the person ends up in no other current family)
is deliberately allowed with no transition record. This makes the "ghost member" case a DB-level
invariant rather than something a repair script has to patch — the old `database/fixes/` script
for it no longer exists.

## What These Tables Are For

Per the frozen "Family First Model" principle, a family is a first-class entity independent of
membership — a Person may belong to a Family without ever becoming an NSS Member. These tables
implement that:

- **`family_group`** — the family record itself: a `family_name`, the Sakha `organization` it is
  registered under (`sakha_organization_pk`), a lifecycle status resolved through Foundation's
  unified `STATUS` category (not a dedicated Family status master), and an optional
  `formed_date`. This is the root of the module — every other table hangs off
  `family_group_pk`.
- **`family_relationship`** — the membership-of-a-family-unit table: one row per (family, person,
  relationship type) linking a `person` into a `family_group` with a relationship type resolved
  through Foundation's `RELATIONSHIP_TYPE` master_data category (FATHER, MOTHER, SPOUSE, SON,
  DAUGHTER, etc. — the same category Person's emergency-contact relationship field also draws
  from) and an effective-dated period (`effective_from`/`effective_to`/`is_current`).
- **`family_head_history`** — an append-only log of who has headed a family and when
  (`effective_from`/`effective_to`), never overwritten in place — this is the "History Never
  Deleted" principle applied to family headship.
- **`family_transition_history`** — an append-only log of a person moving from one family group to
  another (marriage, new family formation, change of family unit), preserving both the
  `old_family_group_pk` and `new_family_group_pk` rather than mutating `family_relationship` rows
  in place.
- **`family_link`** — direct `PARENT_OF`/`SPOUSE_OF` edges between two persons in a family, used
  exclusively to compute *extended* kinship labels (Grandfather, Cousin, Sister-in-Law, ...)
  dynamically via graph traversal relative to a viewer (`api/services/family_graph.py`), rather
  than storing every possible relationship label as data. See "Is `family_relationship`
  superseded by `family_link`?" below — it is not; the two tables serve different, coexisting
  purposes.
- **`family_admin`** — (Tier 5) tracks Family Admin role assignments,
  independent of `family_head_history`: a person may be Head, Admin, both, or neither at once.
  Multiple admins per family are allowed. Only the current Family Head may assign/revoke an
  admin (enforced in `api/routers/family.py`'s `POST`/`DELETE /families/{pk}/admins`, FAM-046/
  FAM-050 — not a DB constraint); a partial unique index
  (`uq_family_admin_current`) allows at most one *current* (`effective_to IS NULL`) admin row
  per (`family_group_pk`, `person_pk`) pair, but does not itself limit how many distinct people
  can be current admins of the same family. **Has 3 API endpoints as of the Tier 5**
  (`GET/POST/DELETE /api/v1/family/families/{pk}/admins`) — not DDL-only; the head-only
  appoint rule is exercised in `tests/api/test_family_ownership.py`.

## Is `family_relationship` superseded by `family_link`?

**No — both tables are live and serve different purposes; `family_link` does not replace
`family_relationship`.** Verified directly against how `api/routers/family.py` queries each:

- `family_relationship` remains the table for *family-unit membership and static relationship
  type*: `_MEMBER_SELECT`/`_FAMILY_SELECT`'s `family_majority` CTE query it for
  `GET /families/{pk}/members`, and the Sakha Alignment endpoint
  (`GET /families/{pk}/sakha-alignment`) queries it directly to enumerate a family's current
  members. It is also what `family_head_history`/`is_head` joins against by
  `(family_group_pk, person_pk)`.
- `family_link` is read by the graph endpoint (`GET /families/{family_group_pk}/graph`) via dedicated
  fragments (`_GRAPH_PERSONS_SQL`/`_GRAPH_LINKS_SQL`, plus `_ORIGIN_ARRIVED_LINKS_SQL` for members
  who moved families) that fetch raw `PARENT_OF`/`SPOUSE_OF` edges and hand them to
  `api/services/family_graph.py`'s `build_family_graph()` for BFS traversal. It is written by
  `create_family` (initial edges), `add_family_member` (`POST /families/{pk}/members`, optional
  `link_type`), `create_family_link` (`POST /families/{pk}/links`) and the move/remove flows, which
  soft-delete a leaving person's edges.

In short: `family_relationship` answers "who belongs to this family, and what is their
relationship-type code" (a flat, category-driven membership list); `family_link` answers "what
are the direct parent/spouse edges between these specific people" (a graph structure used purely
to *derive* every other kinship label on demand). A family's `family_relationship` rows and its
`family_link` rows are populated independently and are expected to coexist for the same family.

## Key FK Relationships

- `family_group.sakha_organization_pk` → `nss.organization(organization_pk)` — the Sakha a family
  is registered under.
- `family_group.family_status_master_data_pk` → `nss.master_data(master_data_pk)` — the unified
  `STATUS` category, same pattern as `organization.status_master_data_pk`. No dedicated
  `family_status_master` table exists — per the frozen "Master Data Driven" principle, one
  generic `master_category`/`master_data` pair serves every module's classification needs.
- `family_relationship.family_group_pk` → `family_group(family_group_pk)`; `person_pk` →
  `nss.person(person_pk)`; `relationship_type_master_data_pk` → `nss.master_data(master_data_pk)`
  (category `RELATIONSHIP_TYPE`).
- `family_head_history.family_group_pk` → `family_group(family_group_pk)`; `person_pk` →
  `nss.person(person_pk)`.
- `family_transition_history.old_family_group_pk` and `.new_family_group_pk` both →
  `family_group(family_group_pk)` (two separate FKs to the same table); `person_pk` →
  `nss.person(person_pk)`.
- `family_link.family_group_pk` → `family_group(family_group_pk)`; `person_a_pk` and
  `person_b_pk` both → `nss.person(person_pk)` (two separate FKs to the same table, the same
  "two FKs, one target" idiom `family_transition_history` uses for its two family-group FKs).
- `family_admin.family_group_pk` → `family_group(family_group_pk)`; `.person_pk` →
  `nss.person(person_pk)`; `.appointed_by_person_pk` → `nss.person(person_pk)` (a second FK to
  the same table — the person, must be the Family Head at the time, who made the appointment).

Like `organization` and `person`, audit-actor FKs (`created_by_sangha_sevi_pk`,
`updated_by_sangha_sevi_pk`, `deleted_by_sangha_sevi_pk`) are nullable plain UUID columns in
the table DDL; their FKs to `sangha_sevi` are added by the single catalog-driven patch
`database/ddl/13_audit_actor_fk/01_audit_actor_fk_patch.sql` (build Phase 13c).

## Non-Obvious Constraints

- **`chk_family_group_soft_delete`** — the standard `(is_active = TRUE AND deleted_at IS NULL) OR
  (is_active = FALSE AND deleted_at IS NOT NULL)` pattern shared with `organization`.
- **`uq_family_rel_person_current`** — a **partial unique index**, not a table-level constraint:
  `UNIQUE (family_group_pk, person_pk) WHERE is_current = TRUE`. A person may have multiple
  historical relationship rows in the same family (e.g. a status change), but only one row per
  (family, person) pair may be flagged current at a time — the same partial-unique-index
  technique Person uses for `uq_person_primary_address`.
- **`chk_family_rel_current_consistency`** — ties `is_current` to `effective_to`: a current
  relationship must have `effective_to IS NULL`, and a historical one must have it set. This
  keeps "is this relationship active right now" derivable from either column without them
  drifting out of sync.
- **`uq_family_head_current`** — another partial unique index: `UNIQUE (family_group_pk) WHERE
  effective_to IS NULL`. At most one row per family group may be the *current* head (no
  `effective_to`); every past head has an `effective_to` set and is never deleted, only
  superseded by a new row.
- **`chk_family_trans_different_families`** — `CHECK (old_family_group_pk <> new_family_group_pk)`
  on `family_transition_history`: a transition record must actually move a person between two
  distinct family groups; a no-op "transition" to the same family is rejected at the DB level.
- **`chk_family_trans_type`** — a `CHECK (transition_type IN ('MARRIAGE',
  'NEW_FAMILY_FORMATION', 'CHANGE_OF_FAMILY_UNIT', 'OTHER'))` enumeration. Unlike relationship
  type or family status, transition type is **not** resolved through Foundation `master_data` —
  it's a plain `VARCHAR(50)` with a CHECK constraint, since it's a closed, small, code-only set
  with no display-name/description/sort-order metadata worth modeling as reference data.
- **`chk_family_link_type`** — `CHECK (link_type IN ('PARENT_OF', 'SPOUSE_OF', 'SIBLING_OF'))` (declared in `CREATE TABLE`; a fresh build gets the full list, no separate `ALTER`), the same
  CHECK-not-master_data closed-enum treatment as `transition_type` above.
- **`chk_family_link_no_self`** — `CHECK (person_a_pk <> person_b_pk)`: a person cannot be
  recorded as their own parent or spouse.
- **`chk_family_link_current_consistency`** — the same `is_current`/`effective_to` pairing idiom
  as `chk_family_rel_current_consistency` above, applied to `family_link`.
- **`uq_family_link_current`** — a third partial unique index in this module: `UNIQUE
  (family_group_pk, person_a_pk, person_b_pk, link_type) WHERE is_current = TRUE`. Prevents the
  same directed edge from being recorded twice while current, without blocking a historical
  (superseded) duplicate from coexisting with its replacement.
- **Business identifier format** — `family_group.family_id` (e.g. `F1`) follows the project-wide
  unpadded ID convention adopted across this branch (see
  `docs/00_Project_Governance/STD/01_project_standards.md` and
  `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md`) — not zero-padded (`F00000001`), per
  the `id_sequence_master` DDL's loosened `CHECK (padding_length BETWEEN 0 AND 12)` constraint.
- **`uq_family_admin_current`** — a fourth partial unique index in this module: `UNIQUE
  (family_group_pk, person_pk) WHERE effective_to IS NULL`. Prevents the same person from being
  recorded as a *current* admin of the same family twice, but does not cap the number of
  distinct current admins per family (multiple admins are allowed, per the file header).
  `family_admin` has no `is_active`/soft-delete column at all — revocation is expressed purely
  via `effective_to`, unlike every other table in this module.

Matches `docs/03_Solution/modules/family/05_family_table_design.md` (SOL-FAM-005) closely — see
that doc for full design rationale. As of this writing that module doc set is still `Status:
DRAFT` (v1.0/v1.0.0), even though its table/column shapes already match this implemented DDL
1:1; it has not yet been reconciled to `FROZEN` the way Person's module docs were before
`03_person/` was built. `family_link` predates any corresponding SOL-FAM-005 update — it was
added under its own separate `ERP-DECISION` authority (see its file header), not as part of that
module doc set. See also `docs/PROJECT_DOCUMENTATION.md` for the tier-by-tier plan.
