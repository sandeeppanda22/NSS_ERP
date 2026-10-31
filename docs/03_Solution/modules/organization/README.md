# NSS ERP Organization Module

Version: 1.1.0

Status: DRAFT — overview/ERD at SOURCE ALIGNED v1.0.0, lifecycle/business-rules/table-design at
GOVERNANCE ALIGNED v1.1.0. **The generic 3-table structure this design freezes is no longer what
is SQL Implemented** at `database/ddl/02_organization/` — see "SQL Implementation" below for the
current state and `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas for the full
reconciliation status; the still-open items (type-to-type parent matrix, `organization_code`
naming) are unaffected.


> **Amendment (2026-10-30, owner-directed, GDR-005):** the Organization type list gains a 14th type, `ADVISORY_BOARD` ("Advisory Board") — a singleton (code `ADB`, short_code `NSSAB`, parent `KENDRA`, name immutable, at most one active row enforced by trigger `nss.fn_enforce_organization_singleton`, which also enforces single active `KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA` and one central Kendra-parented `MAHILA_SANGHA` — owner amendment 2026-10-30; local per-Sakha Mahila Sanghas are unrestricted). The Advisory Board *governance body* remains NSS-wide/NULL-organization. Where this document lists a fixed set of types, read it as extended by this amendment. See `docs/00_Project_Governance/GDR/GDR-005_Advisory_Board_as_a_Singleton_Organization.md`.

> **Amendment (2026-10-31, owner-directed, GDR-008):** the type-to-type parent matrix (ORG-BR-091/092/094) is widened: `KUMARI_SANGHA`, `SEVAK_SANGHA`, the local per-Sakha `MAHILA_SANGHA` and `PARIBARIK_ASANA` may be parented by a Sakha-like organization — `SAKHA_SANGHA` **or** `SAKHA_ASANA` (the `MAHILA_SANGHA` `KENDRA` tier and its singleton rule are unchanged). No schema change: the self-FK `parent_organization_pk` is type-agnostic. See `docs/00_Project_Governance/GDR/GDR-008_Sakha_Asana_Is_a_Sakha_for_All_Organizational_Purposes.md`.

---

## Documents

`01_organization_module_overview.md` (SOL-ORG-001) — module purpose and scope.

`02_organization_erd.md` — entity relationship design for `organization_type_master`,
`organization_status_master`, `organization` (three tables only — no separate
`organization_address` table; address is inline on `organization`).

`03_organization_lifecycle.md` — organizational lifecycle states.

`04_organization_business_rules.md` (SOL-ORG-004) — 86 rules, ORG-BR-001–ORG-BR-086,
GOVERNANCE ALIGNED against GOV-002.

`05_organization_table_design.md` (SOL-ORG-005) — logical table design; self-referencing
hierarchy via `parent_organization_pk`, single apex, `hierarchical_level` as a required logical
attribute (physical type still deferred).

---

## What changed in v1.1.0 (GOVERNANCE ALIGNED)

The prior version's business rules hard-coded specific type-to-type parent constraints
(e.g. "ANCHALIKA must belong to KENDRA", "PATHA_CHAKRA must belong to a SAKHA" — the latter
already inconsistent with the module's own hierarchy diagram). **v1.1.0 explicitly removed
these as frozen facts** — §22 "Rules Explicitly Not Assumed" in
`04_organization_business_rules.md` now lists the exact type-to-type parent compatibility
matrix and the exact `organization_type_master` seed values as open, not frozen. Only the
generic structure remains frozen: single apex root, `parent_organization_pk` self-reference,
three tables, no `organization_address` table. "GOV-002 fully reconciled" means the 3-table
design (parent FK + `hierarchical_level` attribute) was confirmed to satisfy GOV-002's parent/
child/lineage/level/status requirements without adding a 4th table.

**Do not treat `CLAUDE.md`'s ANCHALIKA/ZILLA/SAKHA/PATHA_CHAKRA hierarchy description as
frozen against this doc set** — the type-to-type parent compatibility matrix remains open,
but the **8 organization types themselves are now FROZEN**:
KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA (unique), ANCHALIKA, ZILLA, SAKHA, SAKHA_ASANA,
PATHA_CHAKRA (multiple instances). See ORG-BR-064 for details and ID prefix assignments.

---

## Current Status

Design Complete · ERD Complete · Lifecycle Complete · Business Rules GOVERNANCE ALIGNED ·
Table Design GOVERNANCE ALIGNED · **SQL Implemented — but no longer as 3 tables** (see "SQL
Implementation" below: only `organization` remains as Organization-specific SQL; type/status are
now Foundation `master_data` rows) ·
**API/UI Implementation Complete** — `api/routers/organization.py` exposes 6 read-only
endpoints (`/types`, `/statuses`, `/organizations` list/detail/children, `/hierarchy` via a
`WITH RECURSIVE` CTE), consumed by `frontend/admin.html`'s Organizations and Organization
Hierarchy tabs (originally the 3-tab `frontend/organization.html` verification UI — Reference
Data, Organizations, Hierarchy — since retired and deleted) and verified by 51 pytest integration
tests
(`tests/test_organization.py`); see `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` and
`docs/03_Solution/code_explanations/API_CODE_EXPLANATIONS.md`. Merged to `main` and released as
v0.8.0.

---

## SQL Implementation

**This module's own frozen v1.1.0 design specifies 3 tables** (`organization_type_master`,
`organization_status_master`, `organization`) as the generic structure satisfying GOV-002. **A
later migration retired the two master tables**, replacing their rows with entries in
Foundation's generic `master_data` (categories `ORGANIZATION_TYPE`, 10 values; `STATUS`, a
unified cross-module category also covering the former `MEMBERSHIP_STATUS`, 13 values) —
consistent with the project's frozen "Master Data Driven" principle, but no longer matching this
module's own frozen table design. `database/ddl/02_organization/` now defines only
`organization` (self-referencing `parent_organization_pk`, address inline, no
`organization_address` table, no stored `hierarchical_level` column), which references
`master_data` via `organization_type_master_data_pk`/`status_master_data_pk`. This divergence
between the frozen 3-table design and the implemented 1-table + `master_data` schema has not
been reconciled by a governance decision either way — see
`docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas (the
`organization_type_master`/`organization_status_master` retirement entry) for the full
reconciliation status, including the other frozen documents (`FK_DEPENDENCY_GRAPH.md`,
`DDL_CREATION_ORDER.md`, the Governance Baseline's naming/master-data-catalogue docs) that still
describe the old 3-table physical schema.

Three other things this does **not** resolve, all still open:

- **`organization_code` vs. `organization_short_code`.** `ORG-PENDING-001`
  (`CROSS_MODULE_PRINCIPLES.md` §20.1) froze a column named `organization_short_code`,
  `VARCHAR(5)`, `UNIQUE`, `NOT NULL`. The implemented column is named `organization_code`,
  `VARCHAR(10)`, `UNIQUE`, **nullable**. Same purpose, different name/width/nullability — not
  yet reconciled with the frozen cross-module spec.
- **Seeded type codes don't match this doc's short-form codes.**
  `database/seed/01_foundation/02_master_data.sql` (formerly `database/seed/
  02_organization/01_organization_type_master.sql`, retired by the `master_data` migration)
  seeds `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/
  `SAKHA_SANGHA` (plus `SAKHA_ASANA`/`PATHA_CHAKRA`, which do match) — this doc and
  `04_organization_business_rules.md` describe the short forms `ANCHALIKA`/`ZILLA`/`SAKHA`.
- **Seeded status includes `SUSPENDED`, which the docs explicitly say is unsupported.**
  `database/seed/01_foundation/02_master_data.sql` (formerly `database/seed/
  02_organization/02_organization_status_master.sql`, retired by the `master_data` migration)
  seeds `SUSPENDED` as one of the unified `STATUS` category's 13 values. But
  `03_organization_lifecycle.md` §81 ("No Unsupported States") and
  `04_organization_business_rules.md` ORG-BR-059 ("No Unsupported Status") both explicitly list
  `SUSPENDED` as an example status the design does **not** introduce without an approved
  governance change. The seed data and the frozen business rule currently contradict each other
  — not reconciled here.

See `docs/PROJECT_DOCUMENTATION.md` → Open questions / TODOs for all four.

---

## Note

A prior Django prototype (`backend/foundation/models.py`, a much simpler `Organization`
placeholder — no hierarchy, no self-reference) predated this design but was removed along with
the rest of the Django prototype (`backend/`) — see CLAUDE.md and
`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md`. It is preserved in Git history only,
not on disk. The real implementation is now the SQL DDL at `database/ddl/02_organization/` plus
Foundation's `master_data` for type/status
(see "SQL Implementation" above), not any Django model.
