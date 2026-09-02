# docs/03_Solution/modules/

Per-module Solution design docs. Most modules follow a `01_module_overview` / `02_erd` /
`03_lifecycle` (or `03_business_rules`) / `04_business_rules` / `05_table_design` pattern (a few
older/simpler modules use a 4-file `01_design`/`02_erd`/`03_business_rules`/`04_table_design`
pattern instead — see each module's own `README.md`, the numbering is not uniform across
modules).

Every module below has a complete Solution-level doc set except `family`
(4-file, DRAFT, not yet promoted to a version-tagged status) — nearly all others are tagged
`v1.0.0 DRAFT — SOURCE ALIGNED` (a content-freeze tag, not a lifecycle/Status promotion; the
document-level `Status` field remains `DRAFT` throughout). **None of this documentation has a
matching backend implementation beyond the 5 pre-existing Django apps** (`foundation`,
`authentication`, `family`, `membership`, `heritage`) and the SQL DDL under `database/ddl/`
(`01_foundation/` — fully implemented, 12 tables; `03_person/` — superseded
prototype) — see `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas / Open questions before
assuming any of this is built. **`finance/` (20th module)** follows the same
design-only pattern. **`programmes_events/` (21st module — Module #21)**
remains v0.1.0 DRAFT with "FORMAL MODULE FREEZE PENDING" — all 7 of its reconciliation gates
against other modules are closed (`SOL-EVT-007`; its candidate-table set stands at 7); the
module itself still awaits formal freeze.
**`assets_property/` (22nd module — Module #22)** is tagged
`v1.0.0 DRAFT — SOURCE ALIGNED` like most others. Six modules (`person`, `family`, `governance`,
`attendance`, `authentication`, `administration`) each have a new `_lifecycle.md` document,
shifting their existing business-rules/table-design
file numbers down one slot — check each module's own `README.md` for its current exact file list
before referencing a filename by number. A cross-module architecture pass
(`CROSS_MODULE_PRINCIPLES.md`, `ARCH-CROSS-001`) reassigned `document_master` from Person to
Foundation and split RBAC-adjacent table ownership more precisely between Authentication and
Administration — both reflected in the rows below.

| Module | Design status | Backend/DDL reality |
|---|---|---|
| `organization/` | v1.1.0, GOVERNANCE ALIGNED — type-to-type parent matrix explicitly OPEN | `backend/foundation.Organization` is a simpler placeholder; `database/ddl/02_organization/` is empty |
| `person/` | v1.0.0, SOURCE ALIGNED — **1 table** (`person` only — `document_master` reassigned to Foundation, `DOC-ARCH-001`), 5 files | `database/ddl/03_person/` implements `person`/`person_address` (as `person_code`, docs say `person_id`) |
| `membership/` | v1.0.0, DRAFT — 5-file, ~10 tables designed | `backend/membership/models.py` — 3 simple models only |
| `family/` | v1.0.0, DRAFT — 5-file (includes lifecycle doc SOL-FAM-005), frozen 4-table design | `backend/family/models.py` — 2 simple models only |
| `attendance/` | v1.0.0, DRAFT — 6-file (includes lifecycle doc SOL-ATT-006; Review Workflow FROZEN) + `DARSHAK_BUSINESS_RULE.md` | `backend/attendance/` is an empty stub |
| `heritage/` | v1.0.0, SOURCE ALIGNED — 8 tables | `backend/heritage/` implements only `founder_master` |
| `kumari/` | v1.0.0, SOURCE ALIGNED — 5 tables | no `backend/kumari/` app |
| `kishor/` | v1.0.0, SOURCE ALIGNED — Guardian Model v2.1 frozen | no `backend/kishor/` app |
| `mahila/` | v2.1.0, BYE-LAW ALIGNED — one Governing Body = Mandali, **2-year** term (MAH-040) | no `backend/mahila/` app |
| `sevak/` | Mixed — only `06_sevak_table_design.md` FROZEN, rest DRAFT/consolidation; SEV-024/025/032 identifier-collision question formally CLOSED | no `backend/sevak/` app |
| `foundation/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — describes **10 tables**: the original 8 (master data/geography/sequences) plus shared-infrastructure `document_master` and `field_change_log` (`DOC-ARCH-001`) — **not the same scope as `backend/foundation/`**, see its README | `database/ddl/01_foundation/` **fully implemented** with **12 tables** — all 10 designed tables plus 2 more (`postal_code`, `city_village_postal_code_map`) the design doc doesn't yet describe |
| `administration/` | v1.0.0, SOURCE ALIGNED — **8 Administration-owned tables**: 5 RBAC (`role_master`, `permission_master`, `role_permission`, `user_role`, `admin_scope`) + 3 Correspondence Register tables (`correspondence`, `correspondence_document`, `correspondence_finance_reference`, `SOL-ADMIN-006`–`009`, `CORR-DECISION-003`); `user_account`/`password_history` are exclusively Authentication-owned (frozen) | no `backend/administration/` app |
| `authentication/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — exclusively owns `user_account`+`password_history` (frozen); references the 5 Administration RBAC tables rather than owning them — **different schema from** `backend/authentication/`'s real `Role`/`UserRole`/`LoginAudit` models | `backend/authentication/` exists with an unrelated schema |
| `governance/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — Unified Body Governance Model, 9 tables, now 5 files (includes lifecycle doc SOL-GOV-005) — **freezes Mandali term at 3 years AND a formal election-based reconstitution process**, both conflicting with `mahila/`'s frozen 2-year term and consensus-based process (unreconciled) | `backend/governance/` is an empty stub |
| `publications/` | v1.0.0, SOURCE ALIGNED + USER REQUIREMENTS — 7 files, **zero new tables** (reuses heritage's) | no `backend/publications/` app |
| `upbs/` | v1.0.0, SOURCE ALIGNED — 7 tables | no `backend/upbs/` app |
| `reports/` | v1.0.0, SOURCE ALIGNED — 5 metadata-only tables | no `backend/reports/` app |
| `audit/` | v1.0.0, SOURCE ALIGNED — 2 tables | no `backend/audit/` app |
| `backup_technical/` | v1.0.0, SOURCE ALIGNED — 2 tables | no corresponding Django app |
| `finance/` | v1.0.0, SOURCE ALIGNED — 7 tables (financial_year/scope/fund_master/transaction/receipt/payment/transfer), `_code` convention followed correctly | no `backend/finance/` app |
| `programmes_events/` | v0.1.0, DRAFT — NOT FROZEN (Module #21) — **7 candidate common tables** (`programme_type`, `event`, `event_day`, `event_session`, `event_registration`, `event_location`, `event_history`), none frozen DDL, but all 7 cross-module reconciliation gates are closed (`SOL-EVT-007`); Programme Type → Event Instance two-level model | no `backend/programmes_events/` app |
| `assets_property/` | v1.0.0, DRAFT — SOURCE ALIGNED (Module #22) — 7 tables (`property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`); 74 business rules (`AP-001`–`AP-074`) | no `backend/assets_property/` app |

See `docs/PROJECT_DOCUMENTATION.md` → `03_Solution/` detail for the full breakdown, and its
"Open questions / TODOs" section for open reconciliation items (Mandali term-length AND
process-model conflict, `foundation`/`authentication` naming collisions, `person_id`/
`person_code`, organization type matrix, six new lifecycle docs not cross-referencing
`SOL-LIFE-001`/`002`).
