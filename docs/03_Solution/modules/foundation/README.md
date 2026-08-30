# NSS ERP Foundation Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0. Full Solution design complete (4 files).

**Naming collision — read before assuming anything.** This Solution-layer "Foundation" module
is **not** the same thing as the `backend/foundation/` Django app. They share a name but cover
different scope:

- **This doc set** (`SOL-FND-001`…`004`) designs shared technical/master-data infrastructure —
  master data catalog, system settings, ID sequencing, and the geographic reference hierarchy
  (Country → State → District → City/Village). It matches `database/ddl/01_foundation/`
  (`id_sequence_master`, `country`/`state`/`district`/`city_village`), not the Django app.
- **`backend/foundation/`** (Django app) implements `OrganizationType`, `Organization`,
  `Address`, `Person` models — i.e. the *Person* and *Organization* domains, which have their
  **own**, separate Solution doc sets: `docs/03_Solution/modules/person/` and
  `.../organization/`.

Person and Organization design content does **not** live in this folder — see those two module
folders instead.

---

## Documents

01_foundation_module_overview.md (`SOL-FND-001`) — Version 1.0.0
Purpose: Shared technical/business foundation for other modules — "Configure Once" master-data
and infrastructure capabilities, not a business-operation module itself.

02_foundation_erd.md — Version 1.0.0
Purpose: Entity relationship design for the original eight foundation tables.

03_foundation_business_rules.md — Version 1.0.0, FND-BR-001–FND-BR-084
Purpose: Business rules — Master Data Driven architecture, Configuration Over Hardcoding,
central ID sequence infrastructure. No invented columns/data types — exact VARCHAR lengths,
setting-value representation, and sequence implementation are all marked pending.

04_foundation_table_design.md — Version 1.0.0
Purpose: Physical table design — now **ten** tables (see Key facts): the original eight, plus
two shared-infrastructure tables added 2026-08-26 by `CROSS_MODULE_PRINCIPLES.md`
(`DOC-ARCH-001`, `ARCH-CROSS-001`): `document_master` (reassigned here from Person) and
`field_change_log` (new). §40/§41 of this document record the reassignment and note that the two
tables' logical column designs are defined by Person (for `document_master`) and the Data
Change Architecture (for `field_change_log`) respectively, while Foundation owns the physical
DDL for both.

---

## Key facts

- **Ten tables**: the original eight — `master_category`, `master_data`, `system_setting`,
  `id_sequence_master`, `country`, `state`, `district`, `city_village` — plus two
  shared-infrastructure tables added 2026-08-26: `document_master` (a common document registry;
  Person, Heritage, and Publications are consumers, not owners) and `field_change_log`
  (business-significant field-level change tracking, distinct from module-owned `_history`
  tables).
- Geographic hierarchy (Country→State→District→City/Village) is explicitly **separate** from
  the NSS organizational hierarchy (Kendra→Anchalika→Zilla→Sakha) — see `CLAUDE.md` §7
  Organization paragraph. Do not conflate the two.
- Central RBAC consumption and History Never Deleted / soft delete established here as
  foundation-level principles other modules build on.

## Note — SQL status

`database/ddl/01_foundation/` already implements `id_sequence_master` and the
country/state/district/city_village location tables — this design's core tables are the
*most* SQL-aligned of any new module doc set added this pass. `master_category`,
`master_data`, `system_setting`, `document_master`, and `field_change_log` have no SQL
counterpart yet.

---

## Current Status

Design Complete · ERD Complete (ERD not yet updated for the 2 new shared-infrastructure tables
— see Note below) · Business Rules Drafted (SOURCE ALIGNED) · Table Design Drafted (SOURCE
ALIGNED, now 10 tables) · SQL Implementation Partial (id_sequence/location tables exist; the
other six, including the two added 2026-08-26, do not)
