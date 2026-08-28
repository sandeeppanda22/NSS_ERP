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
Purpose: Entity relationship design for the eight frozen foundation tables.

03_foundation_business_rules.md — Version 1.0.0, FND-BR-001–FND-BR-084
Purpose: Business rules — Master Data Driven architecture, Configuration Over Hardcoding,
central ID sequence infrastructure. No invented columns/data types — exact VARCHAR lengths,
setting-value representation, and sequence implementation are all marked pending.

04_foundation_table_design.md — Version 1.0.0
Purpose: Physical table design — eight tables.

---

## Key facts

- Eight tables: `master_category`, `master_data`, `system_setting`, `id_sequence_master`,
  `country`, `state`, `district`, `city_village`.
- Geographic hierarchy (Country→State→District→City/Village) is explicitly **separate** from
  the NSS organizational hierarchy (Kendra→Anchalika→Zilla→Sakha) — see `CLAUDE.md` §7
  Organization paragraph. Do not conflate the two.
- Central RBAC consumption and History Never Deleted / soft delete established here as
  foundation-level principles other modules build on.

## Note — SQL status

`database/ddl/01_foundation/` already implements `id_sequence_master` and the
country/state/district/city_village location tables — this design's core tables are the
*most* SQL-aligned of any new module doc set added this pass. `master_category`,
`master_data`, and `system_setting` have no SQL counterpart yet.

---

## Current Status

Design Complete · ERD Complete · Business Rules Drafted (SOURCE ALIGNED) · Table Design
Drafted (SOURCE ALIGNED) · SQL Implementation Partial (id_sequence/location tables exist;
master_category/master_data/system_setting do not)
