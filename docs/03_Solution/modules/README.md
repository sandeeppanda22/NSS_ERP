# docs/03_Solution/modules/

Per-module Solution design docs. Most modules follow a `01_module_overview` / `02_erd` /
`03_lifecycle` (or `03_business_rules`) / `04_business_rules` / `05_table_design` pattern (a few
older/simpler modules use a 4-file `01_design`/`02_erd`/`03_business_rules`/`04_table_design`
pattern instead — see each module's own `README.md`, the numbering is not uniform across
modules).

As of 2026-08-25, every module below has a complete Solution-level doc set except `family`
(4-file, DRAFT, not yet promoted to a version-tagged status) — nearly all others are tagged
`v1.0.0 DRAFT — SOURCE ALIGNED` (a content-freeze tag, not a lifecycle/Status promotion; the
document-level `Status` field remains `DRAFT` throughout). **None of this documentation has a
matching backend implementation beyond the 5 pre-existing Django apps** (`foundation`,
`authentication`, `family`, `membership`, `heritage`) and the partial `person`/`foundation`(01)
SQL DDL — see `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas / Open questions before
assuming any of this is built. **`finance/` (20th module, added 2026-08-21)** follows the same
design-only pattern. **`programmes_events/` (21st module, added 2026-08-25 — Module #21) is the
one exception to the SOURCE ALIGNED pattern**: it is still v0.1.0 DRAFT, explicitly "FORMAL
MODULE FREEZE PENDING," with all 5 of its candidate tables NOT FROZEN. Six other modules
(`person`, `family`, `governance`, `attendance`, `authentication`, `administration`) each just
gained a new `_lifecycle.md` document, shifting their existing business-rules/table-design file
numbers down one slot — check each module's own `README.md` for its current exact file list
before referencing a filename by number.

| Module | Design status | Backend/DDL reality |
|---|---|---|
| `organization/` | v1.1.0, GOVERNANCE ALIGNED — type-to-type parent matrix explicitly OPEN | `backend/foundation.Organization` is a simpler placeholder; `database/ddl/02_organization/` is empty |
| `person/` | v1.0.0, SOURCE ALIGNED — 2 tables, now 5 files (lifecycle doc added, SOL-PER-005) | `database/ddl/03_person/` implements `person`/`person_address` (as `person_code`, docs say `person_id`); no `document_master` |
| `membership/` | v1.0.0, DRAFT — 5-file, ~10 tables designed | `backend/membership/models.py` — 3 simple models only |
| `family/` | v1.0.0, DRAFT — 5-file (lifecycle doc added, SOL-FAM-005), frozen 4-table design | `backend/family/models.py` — 2 simple models only |
| `attendance/` | v1.0.0, DRAFT — 6-file (lifecycle doc added, SOL-ATT-006; Review Workflow FROZEN) + `DARSHAK_BUSINESS_RULE.md` | `backend/attendance/` is an empty stub |
| `heritage/` | v1.0.0, SOURCE ALIGNED — 8 tables | `backend/heritage/` implements only `founder_master` |
| `kumari/` | v1.0.0, SOURCE ALIGNED — 5 tables | no `backend/kumari/` app |
| `kishor/` | v1.0.0, SOURCE ALIGNED — Guardian Model v2.1 frozen | no `backend/kishor/` app |
| `mahila/` | v2.1.0, BYE-LAW ALIGNED — one Governing Body = Mandali, **2-year** term (MAH-040) | no `backend/mahila/` app |
| `sevak/` | Mixed — only `06_sevak_table_design.md` FROZEN, rest DRAFT/consolidation | no `backend/sevak/` app |
| `foundation/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — 8 tables (master data/geography/sequences) — **not the same scope as `backend/foundation/`**, see its README | `database/ddl/01_foundation/` implements id_sequence/location; master_category/master_data/system_setting do not exist |
| `administration/` | v1.0.0, SOURCE ALIGNED — 6 RBAC tables, now 5 files (lifecycle doc added, SOL-ADMIN-005) | no `backend/administration/` app |
| `authentication/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — 7 tables, now 5 files (lifecycle doc added, SOL-AUTH-005) — **different schema from** `backend/authentication/`'s real `Role`/`UserRole`/`LoginAudit` models | `backend/authentication/` exists with an unrelated schema |
| `governance/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — Unified Body Governance Model, 9 tables, now 5 files (lifecycle doc added, SOL-GOV-005) — **freezes Mandali term at 3 years AND a formal election-based reconstitution process**, both conflicting with `mahila/`'s frozen 2-year term and consensus-based process (unreconciled) | `backend/governance/` is an empty stub |
| `publications/` | v1.0.0, SOURCE ALIGNED + USER REQUIREMENTS — 7 files, **zero new tables** (reuses heritage's) | no `backend/publications/` app |
| `upbs/` | v1.0.0, SOURCE ALIGNED — 7 tables | no `backend/upbs/` app |
| `reports/` | v1.0.0, SOURCE ALIGNED — 5 metadata-only tables | no `backend/reports/` app |
| `audit/` | v1.0.0, SOURCE ALIGNED — 2 tables | no `backend/audit/` app |
| `backup_technical/` | v1.0.0, SOURCE ALIGNED — 2 tables | no corresponding Django app |
| `finance/` | v1.0.0, SOURCE ALIGNED — 7 tables (financial_year/scope/fund_master/transaction/receipt/payment/transfer), `_code` convention followed correctly | no `backend/finance/` app |
| `programmes_events/` | **v0.1.0, DRAFT — NOT FROZEN (Module #21)** — 5 candidate common tables (`programme_type`, `event`, `event_session`, `event_location`, `event_history`), none frozen; Programme Type → Event Instance two-level model | no `backend/programmes_events/` app |

See `docs/PROJECT_DOCUMENTATION.md` → `03_Solution/` detail for the full breakdown, and
`CLAUDE.md` §13 for open reconciliation items (Mandali term-length AND process-model conflict,
`foundation`/`authentication` naming collisions, `person_id`/`person_code`, organization type
matrix, six new lifecycle docs not cross-referencing `SOL-LIFE-001`/`002`).
