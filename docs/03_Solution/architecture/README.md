# docs/03_Solution/architecture/

Overall solution architecture documentation (cross-module, above the per-module docs in
`docs/03_Solution/modules/`).

## Files

- **`GETTING_STARTED.md`** — Step-by-step local setup guide: prerequisites, database bootstrap
  (create DB/roles, extensions, `02_build.sh`/`.ps1`, validate, grant backend), API setup
  (`.env`, `06_setup_env.sh`, `pip install`, `uvicorn`), running the pytest suite (counts: `tests/README.md`), and a full
  clean-rebuild procedure with the Phase 0-14 build table and troubleshooting. Overlaps in scope
  with the root `README.md`'s "Getting Started" section and `CLAUDE.md`'s "Setup"/"Database"
  sections — this is the most detailed of the three (covers the Tier 5 writer role, JWT secret,
  admin bootstrap and audit-trigger phases).
- **`DEPLOYMENT_PROCEDURE.md`** (v1.3) — Render.com + Neon.dev deployment guide: env vars
  (incl. the Tier 5 `DB_WRITE_USER`/`DB_WRITE_PASSWORD`/`JWT_SECRET_KEY`), what
  `render_build.sh` runs on every deploy (idempotent re-run of all phases 0-14, admin
  bootstrap, audit trigger), verification, troubleshooting, and the unverified Node.js-on-Render
  risk. Not yet run in production.
- **`MEMBER_DASHBOARD.md`** (`ARCH-DASHBOARD-001`, living document) — architecture and data flow
  of `frontend/dashboard.html`/`dashboard.js`: per-tab API sources, ownership-based endpoint
  gating, family-tree rendering, add/remove family member flow, the embedded Org Dashboard, and
  automatic asset cache-busting.
- **`PERFORMANCE_TUNING.md`** (v1.0) — performance changes behind v0.10.4 (connection pools,
  composite partial indexes for the FAM-036 CTE, multi-worker Uvicorn, non-blocking frontend
  fetches) plus scaling guidance; its frontend file names predate the retirement of the
  standalone verification pages (see its own note).
- **`TECH_STACK_DECISIONS.md`** (v1.3) — Approved technology decision record: database
  (PostgreSQL on Neon.dev), backend (FastAPI 0.136.3 on Render.com/Uvicorn — sole framework, no
  ORM, raw psycopg2; Django was implemented as an early prototype and removed in v1.3's
  Django-to-FastAPI migration), frontend (static HTML served by FastAPI + Tailwind CSS + DaisyUI
  + Alpine.js, replacing Django Templates + HTMX), mobile strategy
  (`TECH-MOB-001`, FROZEN: Flutter, Android + iOS from day one, Hive/Drift offline
  storage — supersedes the previous PWA-first/Capacitor/conditional-Flutter position), git
  remotes/deployment flow, and rejected alternatives (including Django, now that it's been tried
  and departed from).
- **`DEVELOPER_REFERENCE_GUIDE.md`** — Per-module "which document to read before coding" matrix
  following the REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE lifecycle order.
- **`PROGRAMME_EVENT_DOMAIN_MODEL.md`** (`SOL-EVT-001`) — Domain model for Programmes & Events:
  Programme Type, Event Instance, Session, Location; Organization ≠ Location; Patha Chakra is
  an Organization Type, not an Event/Programme Type.
- **`EVENT_ENTITY_RECONCILIATION.md`** (`SOL-EVT-002`) — Reconciles the domain model above
  against UPBS, Kishor, Sevak, Mahila, Finance, and Attendance's own event-shaped entities.
- **`MODULE_DEPENDENCY_MAP.md`** (`SOL-ARCH-007`) — hard-FK/runtime/domain dependency map.
  Status: DRAFT overall (v0.1.0), not frozen. Internally inconsistent on module count: its §61
  status footer says "22 modules including Programme & Events and Assets & Property," but its
  own §3 module-inventory table still lists only 21 rows (no `assets_property` row) and one
  other line in the same file still says "the 21-module dependency map" — not fixed here, flagged
  for a follow-up pass on the file itself.
- **`CROSS_MODULE_PRINCIPLES.md`** (`ARCH-CROSS-001`, v1.1.0) — Project-wide
  architectural principles: one-owner-per-table (`ARCH-001`), cross-module reference not
  duplication (`ARCH-002`), Finance as sole owner of financial transactions (`FIN-ARCH-001`),
  Foundation-owned common document registry (`DOC-ARCH-001` — reassigns `document_master` from
  Person to Foundation, adds a new Foundation-owned `field_change_log` table for
  business-significant field-level change tracking), audit/history/effective-dating boundaries,
  and the Correspondence Register decision (`CORR-DECISION-003`/`CORR-ARCH-001`/`CORR-ARCH-002`
  — see the administration module's README). Status: **FROZEN** for all of the above. Carries
  three explicitly **PENDING — DDL phase** design notes not covered by the FROZEN status:
  `ORG-PENDING-001` (organization short code, 3–5 letters), `MEM-PENDING-001` (local Sakha
  number format + a proposed three-level Sangha Sevi → Sakha Affiliation → Local Number identity
  chain), and `ATT-PENDING-001` (Visitor vs. Approved Darshak threshold — classified as an ERP
  operational refinement, not source-derived; no dedicated counter column planned, threshold is
  derivable from existing attendance records).
- **`IMPLEMENTATION_DEPENDENCY_ORDER.md`** (`SOL-ARCH-008` / `IMPLEMENTATION-TIER-001`) —
  unified 0–13 build order across all 22 modules (Organization at Tier 2, Person at Tier 3,
  Heritage at Tier 7, Programme & Events at Tier 8, Finance at Tier 12; Assets & Property sits
  at Tier 6). Status: FROZEN per the document's own header and §44; its closing §79 status
  summary now carries the unified tier model (FROZEN/v1.0.0/22-modules, 14 tiers 0–13).
- **`FK_DEPENDENCY_GRAPH.md`** (`SOL-ARCH-009`) — Physical FK dependency
  graph ("Gate 8") across all 86 frozen/executable tables (+7 Programme & Events candidate
  tables, not yet executable). Resolves the audit-actor circular-dependency problem
  (`sangha_sevi` needed for audit columns everywhere, but itself depends on Foundation) via a
  two-pass DDL strategy: create tables without audit-actor FKs, then add those constraints in a
  second pass. Topologically sorted (Kahn's algorithm) into 8 depths (0–7), zero cycles.
  Status: FROZEN.
- **`DDL_CREATION_ORDER.md`** (`SOL-ARCH-010`) — The exact numbered
  `CREATE TABLE` sequence for all 86 frozen tables ("Gate 9"), derived from SOL-ARCH-009's
  depth ordering, plus the Pass-2 deferred-constraint list (audit-actor FKs on every table).
  The 7 Programme & Events candidate tables are explicitly listed but marked NOT EXECUTABLE
  until Module #21 is formally frozen. Status: FROZEN. Foundation and Organization are now
  implemented against this order (see `database/README.md`); Bootstrap RBAC's 3 tables have
  DDL implemented and committed, ahead of Foundation in execution phase — see
  `BOOTSTRAP_ARCHITECTURE.md` below.
- **`BOOTSTRAP_ARCHITECTURE.md`** (`SOL-ARCH-011`, FROZEN) — Defines a "Phase 0" that creates
  and seeds `role_master`/`permission_master`/`role_permission` (zero FK dependencies) before
  Foundation, resolving the audit-actor circular dependency (audit columns need a `sangha_sevi`
  identity that itself depends on tables that don't exist yet at that point). Establishes the
  `nss_db_owner` (PostgreSQL DDL owner) vs. `NSS_ERP_ADMIN` (ERP RBAC role, a `role_master` row)
  distinction — the two are explicitly not equivalent, and `NSS_ERP_ADMIN` never bypasses RBAC
  checks. Does not change SOL-ARCH-010's depth/sequence assignments or claim table ownership —
  ownership of the 3 tables remains with Administration
  (`docs/03_Solution/modules/administration/05_administration_table_design.md` §2). Permission
  catalogue, the bootstrap administrator's actual Sangha Sevi identity, and MFA-controlled
  privileged DB access (deferred to a future `SOL-ARCH-012`) all remain PENDING.
- **`PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md`** (`SOL-EVT-006`, v1.1.0) — Final
  compatibility review for the Programme & Events module (Module #21) against every other
  module; concludes "architecturally justified," no hard conflicts. Status header reads
  FROZEN (up from DRAFT v0.1.0) — its closing §80 "Reconciliation Closure"
  note records that all open ownership/migration-strategy risks were resolved by
  `PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md` below. Note: two passages deep in the
  document's original body (§69/§77) still say "no Module #21 decision is frozen by this
  document" / "Module #21 = PROPOSED" — leftover from before the status update, not removed;
  the header/§80 supersede them in intent but the internal inconsistency wasn't cleaned up.
- **`PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md`** (`SOL-EVT-007`, v1.0.0,
  FROZEN) — Closes all 7 outstanding Programme & Events cross-module reconciliation gates
  (Gates A–G): confirms P&E owns a common Event entity, that UPBS/Kishor/Sevak's own
  event-shaped entities become common-Event extensions (not separately absorbed or left
  standalone), that Weekly Sangha Puja stays Attendance-owned with no P&E dependency (Gate F),
  and freezes two sub-principles — `P&E-ARCH-001` (common Registration capability, financial
  transactions still Finance-owned) and `P&E-ARCH-002` (Event Session is optional and
  organiser-defined). The P&E candidate-table set stands at 7 (`event_day` and
  `event_registration` included). The tables themselves remain CANDIDATE, not frozen DDL, pending
  Module #21's own formal freeze — see `docs/03_Solution/modules/programmes_events/README.md`.
- API contracts (Bootstrap, Foundation, Organization, Person) now live under
  `docs/03_Solution/api/` — see that folder's own README, not this one.
- `code_explanations/` moved to `docs/03_Solution/code_explanations/` (see that folder's own
  README).

## Current state vs. these decisions

The Django-to-FastAPI migration (`TECH_STACK_DECISIONS.md` v1.3) has landed: the Django
prototype was fully removed and FastAPI is the sole API layer (`api/`: 137 endpoints across 12
routers at v0.11.0; 241 across 16 routers in the working tree incl. uncommitted Tier 6/9; raw psycopg2, no ORM). Released through `v0.11.0` on
`main`; **Tier 5 (Authentication + Administration, v0.11.0)** — JWT/RBAC, a second write-capable
`nss_db_writer` pool, registration + claim approval, admin/audit routers, a DB-level audit
trigger, a CSP, and a login/register/dashboard/admin frontend (Tailwind/DaisyUI pre-built via
Tailwind CLI, Alpine.js from CDN) that replaced the six standalone Tier 0-4 verification pages.
Implemented SQL covers 47 tables at v0.11.0 (69 in the working tree after Tier 6 Governance/Correspondence/Attendance) across Bootstrap RBAC (3), Foundation (15), Organization (1),
Person (2), Family (6), Membership (14), Authentication (4) and Administration (2); a fresh
build seeds no demo Person/Family/Membership data (only 175 real Sakha branches and one admin
superuser). The pytest suite (1335 test functions; 1638 collected as of 2026-10-28; counts in `tests/README.md`) spans `tests/api/`, `tests/db/`, `tests/security/`
and a Playwright `tests/ui/` layer. Deployment infrastructure (`render.yaml`,
`render_build.sh`) exists but has not yet run in production.

`PROGRAMME_EVENT_DOMAIN_MODEL.md` and `EVENT_ENTITY_RECONCILIATION.md` remain PROPOSED/DRAFT;
`MODULE_DEPENDENCY_MAP.md` (`SOL-ARCH-007`) remains DRAFT overall.
`IMPLEMENTATION_DEPENDENCY_ORDER.md` (`SOL-ARCH-008`), `FK_DEPENDENCY_GRAPH.md`
(`SOL-ARCH-009`), `DDL_CREATION_ORDER.md` (`SOL-ARCH-010`), `BOOTSTRAP_ARCHITECTURE.md`
(`SOL-ARCH-011`), `CROSS_MODULE_PRINCIPLES.md` (`ARCH-CROSS-001`, except its 3 PENDING notes),
`PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md` (`SOL-EVT-006`), and
`PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md` (`SOL-EVT-007`) are FROZEN, alongside the
already-Approved `TECH_STACK_DECISIONS.md`. See `docs/PROJECT_DOCUMENTATION.md` →
Architecture for the current code-verified state and how it differs from these decisions.
