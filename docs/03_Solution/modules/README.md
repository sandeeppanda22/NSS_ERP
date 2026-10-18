# docs/03_Solution/modules/

Per-module Solution design docs. Most modules follow a `01_module_overview` / `02_erd` /
`03_lifecycle` (or `03_business_rules`) / `04_business_rules` / `05_table_design` pattern (a few
older/simpler modules use a 4-file `01_design`/`02_erd`/`03_business_rules`/`04_table_design`
pattern instead — see each module's own `README.md`, the numbering is not uniform across
modules).

Every module below has a complete Solution-level doc set except `family`
(4-file, DRAFT, not yet promoted to a version-tagged status) — nearly all others are tagged
`v1.0.0 DRAFT — SOURCE ALIGNED` (a content-freeze tag, not a lifecycle/Status promotion; the
document-level `Status` field remains `DRAFT` throughout). **The Django prototype (`backend/`)
that once implemented a handful of these modules as simple placeholder models has been removed
from the codebase entirely** (archived in Git history only — see `CLAUDE.md`); the current
implementation is FastAPI (`api/`) + hand-written PostgreSQL DDL (`database/ddl/`), and these
areas have real implemented code: `00_bootstrap/` (RBAC, owned by `administration/`),
`01_foundation/` (15 tables), `02_organization/` (1 table), `03_person/` (`person`, 28 columns,
and `person_address`), `04_family/` (6 tables), `05_membership/` (16 tables),
`06_authentication/` (5 tables), `07_administration/` (`user_role`, `admin_scope`) and — Tier 6,
in progress/uncommitted — `08_governance/` (10 tables). Every other module below (`attendance`,
`heritage`, `kumari`, `kishor`, `mahila`, `sevak`, etc.) is design-only with no implemented code —
see `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas / Open questions before assuming any of
it is built. **`finance/` (20th module)** follows the same
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

| Module | Design status | Implementation reality |
|---|---|---|
| `organization/` | v1.1.0, GOVERNANCE ALIGNED — type-to-type parent matrix explicitly OPEN | `database/ddl/02_organization/` implemented, 1 table (`organization`; type/status masters retired into Foundation `master_data`) |
| `person/` | v2.0.0, FROZEN — **2 tables** (`person`, `person_address` — `document_master` reassigned to Foundation, `DOC-ARCH-001`), 5 files | `database/ddl/03_person/02_person.sql` (28 columns) + `03_person_address.sql` implemented; API (`api/routers/person.py`, 5 endpoints), UI (originally `frontend/person.html`, retired — now `frontend/admin.html`'s Person Directory tab), and tests (`tests/api/test_person.py`) all implemented — `01_person_master_tables.sql` remains a superseded prototype file, not run |
| `membership/` | v1.0.0, DRAFT — 5-file, ~10 tables designed | `database/ddl/05_membership/` implemented, 16 tables (design doc not yet reconciled); API `api/routers/membership.py` (8 endpoints) + `membership_change_request.py` (5, Tier 6) |
| `family/` | v1.0.0, DRAFT — 5-file (includes lifecycle doc SOL-FAM-005), frozen 4-table design | `database/ddl/04_family/` implemented, 6 tables; API `api/routers/family.py` (16 endpoints) |
| `attendance/` | v1.0.0, DRAFT — 6-file (includes lifecycle doc SOL-ATT-006; Review Workflow FROZEN) + `DARSHAK_BUSINESS_RULE.md` | no implementation |
| `heritage/` | v1.0.0, SOURCE ALIGNED — 8 tables | no implementation |
| `kumari/` | v1.0.0, SOURCE ALIGNED — 5 tables | no implementation |
| `kishor/` | v1.0.0, SOURCE ALIGNED — Guardian Model v2.1 frozen | no implementation |
| `mahila/` | v2.1.0, BYE-LAW ALIGNED — one Governing Body = Mandali, **2-year** term (MAH-040) | no implementation |
| `sevak/` | Mixed — only `06_sevak_table_design.md` FROZEN, rest DRAFT/consolidation; SEV-024/025/032 identifier-collision question formally CLOSED | no implementation |
| `foundation/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — describes **10 tables**: the original 8 (master data/geography/sequences) plus shared-infrastructure `document_master` and `field_change_log` (`DOC-ARCH-001`) | `database/ddl/01_foundation/` **fully implemented** with **15 tables** — all 10 designed tables plus `postal_code`, `post_office`, `festival_master`, `festival_calendar_date` and `system_event_log` that the design doc doesn't yet describe (the former `city_village_postal_code_map` was retired) |
| `administration/` | v1.0.0, SOURCE ALIGNED — **8 Administration-owned tables**: 5 RBAC (`role_master`, `permission_master`, `role_permission`, `user_role`, `admin_scope`) + 3 Correspondence Register tables (`correspondence`, `correspondence_document`, `correspondence_finance_reference`, `SOL-ADMIN-006`–`009`, `CORR-DECISION-003`); `user_account`/`password_history` are exclusively Authentication-owned (frozen) | `database/ddl/00_bootstrap/` implements 3 of the 5 designed RBAC tables (`role_master`, `permission_master`, `role_permission`) and `database/ddl/07_administration/` the other 2 (`user_role`, `admin_scope`); API `api/routers/admin.py` + `claim_approval.py`; the Correspondence Register tables are not yet implemented |
| `authentication/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — exclusively owns `user_account`+`password_history` (frozen); references the 5 Administration RBAC tables rather than owning them | `database/ddl/06_authentication/` implemented, 5 tables (`user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session` — the last three beyond the 2 designed); API `api/routers/auth.py` + `registration.py` |
| `governance/` (Solution-layer) | v1.0.0, SOURCE ALIGNED — Unified Body Governance Model, 9 tables designed, now 5 files (includes lifecycle doc SOL-GOV-005) — **freezes Mandali term at 3 years AND a formal election-based reconstitution process**, both conflicting with `mahila/`'s frozen 2-year term and consensus-based process (unreconciled) | Tier 6, in progress/uncommitted: `database/ddl/08_governance/` implements **10** tables (design's 9 + `election_vote_participation`); API `api/routers/governance.py` (46 endpoints) |
| `publications/` | v1.0.0, SOURCE ALIGNED + USER REQUIREMENTS — 7 files, **zero new tables** (reuses heritage's) | no implementation |
| `upbs/` | v1.0.0, SOURCE ALIGNED — 7 tables | no implementation |
| `reports/` | v1.0.0, SOURCE ALIGNED — 5 metadata-only tables | no implementation |
| `audit/` | v1.0.0, SOURCE ALIGNED — 2 tables | no implementation |
| `backup_technical/` | v1.0.0, SOURCE ALIGNED — 2 tables | no implementation |
| `finance/` | v1.0.0, SOURCE ALIGNED — 7 tables (financial_year/scope/fund_master/transaction/receipt/payment/transfer), `_code` convention followed correctly | no implementation |
| `programmes_events/` | v0.1.0, DRAFT — NOT FROZEN (Module #21) — **7 candidate common tables** (`programme_type`, `event`, `event_day`, `event_session`, `event_registration`, `event_location`, `event_history`), none frozen DDL, but all 7 cross-module reconciliation gates are closed (`SOL-EVT-007`); Programme Type → Event Instance two-level model | no implementation |
| `assets_property/` | v1.0.0, DRAFT — SOURCE ALIGNED (Module #22) — 7 tables (`property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`); 74 business rules (`AP-001`–`AP-074`) | no implementation |

See `docs/PROJECT_DOCUMENTATION.md` → `03_Solution/` detail for the full breakdown, and its
"Open questions / TODOs" section for open reconciliation items (Mandali term-length AND
process-model conflict, organization type matrix, six new lifecycle
docs not cross-referencing `SOL-LIFE-001`/`002`).
