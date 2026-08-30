# NSS ERP Organization Module

Version: 1.1.0

Status: DRAFT — overview/ERD at SOURCE ALIGNED v1.0.0, lifecycle/business-rules/table-design at
GOVERNANCE ALIGNED v1.1.0. Designed, **not yet implemented in SQL**
(`database/ddl/02_organization/*.sql` are all 0-byte placeholder files; see
`docs/PROJECT_DOCUMENTATION.md` → Key workflows).

As of this version the module was restructured from its original 4-file
`01_design`/`02_erd`/`03_business_rules`/`04_table_design` pattern to the 5-file pattern below
(matching membership/person/kumari/kishor/mahila) — the old files
(`01_organization_design.md`, `03_organization_business_rules.md`,
`04_organization_table_design.md`) were deleted, not renamed.

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
but the **8 organization types themselves are now FROZEN** (decided 2026-08-28):
KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA (unique), ANCHALIKA, ZILLA, SAKHA, SAKHA_ASANA,
PATHA_CHAKRA (multiple instances). See ORG-BR-064 for details and ID prefix assignments.

---

## Current Status

Design Complete · ERD Complete · Lifecycle Complete · Business Rules GOVERNANCE ALIGNED ·
Table Design GOVERNANCE ALIGNED · SQL Implementation Not Started

---

## Note

Django's `foundation.Organization` model (`backend/foundation/models.py`) is a much simpler
placeholder that predates this design (no hierarchy, no self-reference) — see
`docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas before extending it.
