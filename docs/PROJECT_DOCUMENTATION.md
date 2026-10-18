# NSS ERP — Project Documentation

> Comprehensive, code-verified documentation for the NSS ERP repository. This is the deep
> reference; `CLAUDE.md` is the terse AI-agent operating memory, and `README.md` is the
> public-facing project pitch. Where they disagree with what's actually in the code, this
> document (and the code itself) wins.

---

## Overview

NSS ERP is an in-development Enterprise Resource Planning system for **Nilachala Saraswata
Sangha (NSS)**, a religious/spiritual organization. It is not a generic corporate ERP — its
data model is built around NSS's own statutory structure (Kendra → Anchalika/Zilla →
Sakha), its membership system (Sangha Sevi ID), and organizational concepts like Family,
Governance, Attendance, Mahila Sangha, Kumari Sangha, Kishor Puja, Sevak Sangha, and Founder &
Heritage.

The project follows a **Constitution First → Governance → Requirements → Solution →
Implementation** philosophy, and for delivery, **Database First → API First → UI First**: raw
SQL schema is designed and frozen before API endpoints/schemas are written, and API endpoints
before UI. That philosophy is visible directly in the repo — the `person`, `organization`,
`family`, and `membership` modules all started as hand-written SQL DDL that predated any
API-layer consumption; Tier 2 caught Organization up with a read-only API
(`api/routers/organization.py` — see Architecture and Key Workflow #4 below), Tier 3 did the
same for Person (`api/routers/person.py` — see Key Workflow #5 below; released as v0.9.0), and
Tier 4 has now done the same for Family and Membership (`api/routers/family.py`,
`api/routers/membership.py` — see Key Workflow #6 below; merged and released as v0.10.0, followed
by three hotfix tags v0.10.1-v0.10.3), though several
of all four modules' own design decisions remain open (see Gotchas). A performance-hardening
pass on top of Tier 4 was released as **v0.10.4**, merged from branch `performance-optimization`
(see Gotchas and "Current position" below).

The codebase today spans Tier 0 through the in-progress Tier 5: the read-only Tier 0-4
FastAPI application (`api/`) — 15 routers (12 at v0.11.0 + Tier 6 `governance`, `membership_change_request`, `correspondence`), one per tier/module (endpoint counts per router:
`api/README.md`, `docs/03_Solution/api/API_CONTRACT.md`; no ORM, raw `psycopg2` against `nss.*`) behind a
cross-tier security middleware stack (security headers, opt-in CORS, rate limiting, and now a
Content-Security-Policy — see Architecture below), a growing raw-SQL PostgreSQL schema
(table counts per phase: `database/README.md`; the old superseded Person prototype file
has been deleted; see the `database/` detail below), a `tests/` pytest suite
(four suites — `tests/api/`, `tests/db/`, `tests/security/`, `tests/ui/`; counts live only in `tests/README.md` — see Conventions &
Gotchas and Open questions / TODOs), and an extensive, mature
governance/documentation corpus that is significantly ahead of the code. Solution-layer design
documentation (`docs/03_Solution/modules/`) is complete or near-complete across 22 module
folders — with zero corresponding API/SQL work beyond the Tier 0-4 endpoints
(Bootstrap/Foundation/Organization/Person/Family/Membership) and the matching DDL noted
above. A Django prototype (`backend/`) previously existed
covering `foundation`, `authentication`, `family`, `membership`, and `heritage`, but was fully
archived and removed (`chore: archive and remove Django prototype`) once the FastAPI direction
was adopted — `backend/` has been fully removed from the repository (the directory no longer exists on disk).
`docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` states an `_id` business-identifier
convention that contradicts the project's actual frozen `_code`-only convention — see
Conventions & gotchas. `programmes_events` is the one module not tagged SOURCE ALIGNED (still
DRAFT, not frozen), though its cross-module reconciliation is complete.

**Tier 5 is released as v0.11.0** (merged to `develop` and `main`; the tag exists locally and
must still be pushed). It adds a genuine read-write slice on top of the read-only Tiers 0-4
above: JWT authentication (`api/routers/auth.py`), user/role administration
(`api/routers/admin.py`), self-registration with admin-approval (`api/routers/registration.py`,
`api/routers/claim_approval.py`), an authenticated audit-trail viewer
(`api/routers/audit.py`), a second `nss_db_writer` DB connection pool, 11 new tables
(`user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session`, `user_role`,
`admin_scope`, `family_admin`, `darshak_attendance_registration`, `credential_sequence_counter`, `system_event_log`), later joined by Foundation's `post_office`/`festival_master`/`festival_calendar_date`, plus a
DB-level `fn_audit_trigger()` firing on every `nss.*` table, and four new frontend pages
(`login.html`, `register.html`, `dashboard.html`, `admin.html`). **`claim-approval.html` was
never built as a standalone page** — the claims-review UI for `registration_claim` rows shipped
as a "Registration Approvals" tab inside `admin.html`/`admin.js` instead; this is not a gap.
Later in this same branch's development, `foundation.py`/`organization.py`/`person.py`/
`membership.py` also gained `require_permission("<MODULE>_VIEW")` gating on every GET
endpoint (previously read-only/no-auth throughout Tiers 0-4), `permission_master`/
`role_permission` were seeded, the six standalone Tier 0-4 verification pages
(`index.html`/`foundation.html`/`organization.html`/`person.html`/`family.html`/
`membership.html`, plus their JS) were deleted outright and folded into `admin.html`/
`dashboard.html`, and a Content-Security-Policy was added to `api/middleware.py`. **The
Architecture diagram and Frontend-layer prose immediately below have been updated for the page
retirement and current routing, but still predate the CSP and permission-gating changes** — treat
CLAUDE.md's "Architecture" section (auth model is per-router) as the up-to-date source for exact
current auth behavior. It also
**removes every Tier 4 demo/verification seed file** and `database/migrations/` wholesale, and
rewrites `tests/conftest.py` to use a session-scoped, `SAVEPOINT`-rolled-back write connection
instead of relying on pre-seeded data. See the new "Tier 5" subsection under Architecture below
for the full detail.

## Architecture

```
Browser
   │
   ▼
Security middleware (api/middleware.py + api/main.py) — rate limiting → CORS (if configured) →
security headers
   │
   ├──→ GET /               FastAPI (api/main.py) → RedirectResponse("/login", 302)
   ├──→ GET /login           FastAPI (api/main.py) → FileResponse(frontend/login.html)
   ├──→ GET /register        FastAPI (api/main.py) → FileResponse(frontend/register.html)
   ├──→ GET /dashboard       FastAPI (api/main.py) → FileResponse(frontend/dashboard.html)
   ├──→ GET /admin           FastAPI (api/main.py) → FileResponse(frontend/admin.html)
   ├──→ GET /assets/*        FastAPI StaticFiles mount → frontend/assets/ (incl. pre-built
   │                          tailwind.min.css — see Frontend layer below)
   ├──→ GET /api/v1/bootstrap/...    FastAPI (api/routers/bootstrap.py)
   ├──→ GET /api/v1/foundation/...   FastAPI (api/routers/foundation.py)
   ├──→ GET /api/v1/organization/... FastAPI (api/routers/organization.py)
   ├──→ GET /api/v1/person/...       FastAPI (api/routers/person.py)
   ├──→ GET /api/v1/family/...       FastAPI (api/routers/family.py) → /graph delegates to
   │                                  api/services/family_graph.py (BFS traversal)
   ├──→ /api/v1/membership/...       FastAPI (api/routers/membership.py)
   ├──→ /api/v1/auth/...             FastAPI (api/routers/auth.py) — Tier 5
   ├──→ /api/v1/admin/...            FastAPI (api/routers/admin.py) — Tier 5
   ├──→ /api/v1/register             FastAPI (api/routers/registration.py) — Tier 5
   ├──→ /api/v1/admin/claims/...     FastAPI (api/routers/claim_approval.py) — Tier 5
   └──→ GET /api/v1/audit/...        FastAPI (api/routers/audit.py) — Tier 5
                                │
                                ▼
                    psycopg2 connection pool (api/database.py) — raw SQL, no ORM
                                │
                                ▼
                    PostgreSQL (nss.* schema, hand-written DDL under database/ddl/)
```

- **Security middleware:** registered in `api/main.py`, in order (comments there call out that
  order matters — outermost registered last runs first): (1) `SlowAPIMiddleware` — global rate
  limiting via a module-level `Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])`
  (default `60/minute`, no per-route `@limiter.limit(...)` decorators, so every route shares one
  limit); (2) `CORSMiddleware` — only added `if settings.CORS_ORIGINS:` (comma-separated env var,
  default empty ⇒ middleware never registered at all, `allow_methods=["GET", "POST", "PATCH", "DELETE"]`,
  `allow_credentials=True`, never `allow_origins=["*"]`); (3) `api/middleware.py`'s
  `add_security_headers` — an `app.middleware("http")` function that sets
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and
  `Permissions-Policy: camera=(), microphone=(), geolocation=()` on every response, plus
  `Cache-Control: no-store` scoped to paths starting `/api/` only, and (Tier 5)
  `Cache-Control: public, max-age=86400, must-revalidate` on `/assets/*`; and (4, Tier 5) a Content-Security-Policy via `api/middleware.py::build_csp()` — enabled and
  enforcing by default (`CSP_ENABLED`/`CSP_REPORT_ONLY`/`CSP_SCRIPT_SRC_EXTRA`/
  `CSP_STYLE_SRC_EXTRA` env vars; `script-src` omits `'unsafe-inline'` since all inline event
  handlers were removed from the frontend rather than nonced — see
  `docs/03_Solution/security/TIER5_SECURITY_AUDIT.md` §2.2). Deliberately omits
  `X-XSS-Protection` (obsolete) and HSTS (left to Render's edge TLS). Fully covered by
  `tests/security/test_security_headers.py`. Full
  line-by-line walkthrough: `docs/03_Solution/code_explanations/SECURITY_CODE_EXPLANATIONS.md`
  (not yet updated for CSP/permission-gating — treat as partially stale).
- **Web/API layer:** FastAPI (`api/`), the only web/API layer in the codebase — the earlier
  Django prototype (`backend/`) has been fully removed. `api/main.py` builds the `FastAPI` app
  and includes **15 routers** (12 at v0.11.0, plus Tier 6 `governance`, `membership_change_request`, `correspondence`) via a single `app.include_router(...)` call each:
  `api/routers/bootstrap.py` (prefix `/api/v1/bootstrap`), `api/routers/foundation.py` (prefix
  `/api/v1/foundation`), `api/routers/organization.py` (prefix `/api/v1/organization`),
  `api/routers/person.py` (prefix `/api/v1/person`), `api/routers/family.py` (prefix
  `/api/v1/family`), `api/routers/membership.py` (prefix `/api/v1/membership`), and — Tier 5 (v0.11.0) — `api/routers/auth.py` (`/api/v1/auth`), `api/routers/admin.py`
  (`/api/v1/admin`), `api/routers/registration.py` (`/api/v1/register`),
  `api/routers/claim_approval.py` (`/api/v1/admin/claims`), and `api/routers/audit.py`
  (`/api/v1/audit`) — **endpoints** (see the per-router breakdown in the Overview
  above). `family.py`'s `/graph` endpoint delegates its BFS relationship computation to
  a new `api/services/` layer (`api/services/family_graph.py`, `build_family_graph()` +
  `FamilyGraph.compute_relationships()`) — joined in Tier 5 by
  `api/services/auth_service.py` (Argon2 hashing + JWT issuance) and
  `api/services/rbac_service.py` (`UserContext` + permission/scope loading); no other endpoint
  uses `family_graph.py`. If `frontend/` exists on disk, `api/main.py`
  mounts `frontend/assets/` at `/assets` and serves each of the four remaining HTML pages via its
  own `if <page>_path.is_file(): @app.get(...)` block — a repeated pattern, not one monolithic
  frontend-serving block, so each page is independently gated on that specific file's presence:
  `frontend/login.html` via `GET /login`, `frontend/register.html` via `GET /register`,
  `frontend/dashboard.html` via `GET /dashboard`, and `frontend/admin.html` via `GET /admin`,
  plus an unconditional `GET /` route (registered if `frontend/` is a directory) that
  302-redirects to `/login`. The six original Tier 0-4 page routes (`GET /` →
  `frontend/index.html`, `/foundation`, `/organization`, `/person`, `/family`, `/membership`)
  were deleted along with their pages — see the "Retired standalone verification pages" comment
  in `api/main.py`
  — mounting at `/assets` rather than `/` avoids shadowing FastAPI's own `/docs` (Swagger UI) and
  `/openapi.json`. Swagger UI/ReDoc/OpenAPI schema can be disabled via `DISABLE_DOCS` in
  `api/.env`. The security middleware stack above is registered; authentication/authorization is
  **not** implemented as middleware — it's a per-route FastAPI dependency
  (`Depends(get_current_user)` / `Depends(require_permission(...))`, `api/dependencies/`) layered
  on top. On the Tier 5 (Tier 5) that dependency now gates every
  Foundation/Organization/Person/Membership GET route plus all 16 Family routes (an
  ownership-based model — see the Family section below); only `bootstrap.py`'s 4 endpoints
  remain unauthenticated.
- **Frontend layer:** `frontend/` — four authenticated single-page views built with Tailwind CSS +
  DaisyUI and Alpine.js, no framework: `login.html`, `register.html`, `dashboard.html` (the
  role-aware Member Dashboard — Personal, Family, Membership, Attendance, Governance and
  Documents tabs; the Family tab carries the family-tree/graph visualization consuming `/graph`
  and the Sakha-alignment mismatch badges consuming `/sakha-alignment`), and `admin.html` (the
  Administration Dashboard — Users, User Detail, Create User, Create Sangha-Sevi, Password,
  Create Organization, Organizations, Registration Approvals/Claims, Person Directory, Member
  Directory, Organization Hierarchy, Reference Data, Geography and System Settings tabs). The six
  original Tier 0-4 standalone verification pages — a Tier 0 "Bootstrap Verification UI"
  (`index.html`), a Tier 1 "Foundation Verification UI" (`foundation.html`), a Tier 2
  "Organization Verification UI" (`organization.html`), a Tier 3 "Person Verification UI"
  (`person.html`), and two Tier 4 UIs, a "Family Verification UI" (`family.html`) and a
  "Membership Verification UI" (`membership.html`) — have been **deleted**, together with their
  per-page JS; each one's functionality moved into the `admin.html`/`dashboard.html` tab named
  above. Alpine.js is still CDN-loaded on every page, pinned to `3.14.8` with SRI
  `integrity`/`crossorigin`, unchanged. **Tailwind CSS + DaisyUI moved off the CDN** (new,
  committed, not yet on `main`): all pages now
  `<link rel="stylesheet" href="/assets/css/tailwind.min.css">` instead of the old
  `<script src="https://cdn.tailwindcss.com">` Play-CDN tag plus a DaisyUI CDN `<link>` with an
  SRI hash. `frontend/assets/css/tailwind-input.css` (just the three `@tailwind base/components/
  utilities` directives) is compiled by the Tailwind CLI (`npx tailwindcss -i
  frontend/assets/css/tailwind-input.css -o frontend/assets/css/tailwind.min.css --minify`) into
  `frontend/assets/css/tailwind.min.css` (~87 KB, committed to the repo and NOT gitignored, so a
  fresh clone still works without running Node), driven by root `tailwind.config.js` (content
  globs `./frontend/**/*.html` + `./frontend/assets/js/**/*.js`, `daisyui` plugin, single
  `"light"` theme) and root `package.json` (`devDependencies`: `tailwindcss` `^3.4.17`,
  `daisyui` `^4.12.14`; scripts `css:build`/`css:watch`). `render_build.sh` now runs `npm
  install` + that same `npx tailwindcss ... --minify` build as its first step, before the Python
  dependency install — also Tier 5. `.gitignore` gained a `node_modules/` entry.
  `frontend/assets/js/` now contains `login.js`, `register.js`, `dashboard.js` and `admin.js`
  (the four page components), `auth.js` (`NSSAuth` — JWT storage/refresh + authenticated
  `fetch()` wrapper), and the shared helpers `nss-layout.js`, `nss-config.js`,
  `nss-datepicker.js`, `nss-dialog.js` and `nss-location.js`. The deleted per-page components
  and where their behaviour went: `app.js` (`bootstrapApp()` — `/api/v1/bootstrap/*` system
  status, RBAC roles, permissions, role→permissions drill-down) → `admin.html`'s System Settings
  tab; `foundation.js` (`foundationApp()` — lazy per-tab fetches from `/api/v1/foundation/*`
  across Master Data, System Config, Geographic drill-down, Runtime Tables) → `admin.html`'s
  Reference Data and Geography tabs; `organization.js` (`organizationApp()` — Reference Data,
  Organizations with click-to-drill-down children, Hierarchy tree) → `admin.html`'s
  Organizations and Organization Hierarchy tabs; `person.js` (`personApp()` — Persons with
  filter/detail/addresses drill-down, debounced trigram Search) → `admin.html`'s Person
  Directory tab; `family.js` (`familyApp()` — recursive generation-based family tree from
  `/graph` with a "View As" viewer selector, org-admin drill-down view, Sakha-alignment mismatch
  badges) → `dashboard.html`'s Family tab; `membership.js` (`membershipApp()` — the three-tier
  identity model, Sangha Sevi ID / Sakha Sangha ID / Kendra Number, across a Members tab and a
  trigram/prefix Search tab) → `dashboard.html`'s Membership tab plus `admin.html`'s Member
  Directory tab. See
  `frontend/README.md` for the full file/function/state reference. Served entirely by FastAPI —
  same-origin, so the frontend itself needs no CORS; `CORSMiddleware` above exists for *other*
  (cross-origin) API consumers, and is a no-op locally since `CORS_ORIGINS` defaults to empty.
- **Data layer:** a single track — **hand-written PostgreSQL DDL** under `database/ddl/`,
  following the project's own UUID-`_pk` + business-`_code` convention (see Conventions &
  Gotchas). This is the "real" schema per the governance/standards docs, and it is now consumed
  — read-only — by the FastAPI Tier 0 through Tier 4 endpoints (Bootstrap, Foundation,
  Organization, Person, Family, Membership) via raw parameterized SQL (no ORM). `organization`
  has a read-only API (`api/routers/organization.py`); so do `person` (`api/routers/person.py`),
  `family` (`api/routers/family.py`, 5 tables), and `membership` (`api/routers/membership.py`,
  12 tables) — see "Current position" above.
- **Test layer:** `tests/` — pytest, configured via `pytest.ini` (repo root). `tests/conftest.py`
  wraps `fastapi.testclient.TestClient(app)` against a **real** local PostgreSQL DB (nothing
  mocked); all tests carry the custom `integration` marker. Suites: `tests/api/` (per-router), `tests/db/`
  (schema/data-integrity smoke tests), `tests/security/` (auth gating, CSP/rate-limit/CORS/
  `DEBUG_MODE`) and `tests/ui/` (Playwright). Notable guards: `sequences.current_value` is never
  exposed and `/api/v1/foundation/change-log` must 404/405; Aadhaar ciphertext/hash are never
  returned by Person endpoints; the shared rate-limit `limiter` singleton is reset by an autouse
  fixture in `tests/conftest.py` before *every* test (it's process-wide). Per-file counts and
  coverage: `tests/README.md`.
- **Auth:** none. Tier 0 is explicitly read-only, unauthenticated, by design — RBAC/JWT/OTP
  enforcement is deferred to a later tier, even though
  `docs/00_Project_Governance/STD/05_security_standards.md` specifies a full RBAC +
  Row-Level-Security model as the eventual target.
- **Governance/documentation layer:** a large, independently-maintained set of governance
  standards (`docs/00_Project_Governance/`) and authoritative legal reference documents
  (`docs/01_Authoritative_References/`) that define the rules the eventual system must follow.
  This layer is far more mature than the code.

**Approved future direction (SOLUTION layer, partially implemented in code):**
`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` (v1.5) is the authoritative technology
decision record — FastAPI/Uvicorn is now the sole backend framework (the earlier Django
prototype was implemented, then fully archived and removed as part of v1.3's
Django-to-FastAPI migration) + Tailwind/DaisyUI/Alpine.js UI + Flutter mobile. The FastAPI half
is now implemented through Tier 5 on the feature branch (Bootstrap, Foundation, Organization, Person, Family,
Membership, Auth/Admin/Registration/Claim-approval/Audit), and the Tailwind/DaisyUI/Alpine.js web UI
now consists of `login`/`register`/`dashboard`/`admin` pages under `frontend/` (the six Tier 0-4
verification pages were deleted and folded into `admin.html`/`dashboard.html`); Tailwind/DaisyUI moved from CDN to a
pre-built CLI output (v1.5, committed, see Architecture above and
Gotchas below); the Flutter mobile client remains
unbuilt, and `render.yaml`/`render_build.sh` declare a Render.com + Neon.dev deployment that has
not yet run in production. **Mobile strategy:** the app's own
mobile client is Flutter, targeting Android + iOS from day one (Hive/Drift for offline local
storage, syncing via a Dart background isolate, FCM for push). The web app itself still uses
IndexedDB/Service-Worker offline support for on-site event registration in the browser — a
parallel, not exclusive, path to the Flutter app.
`docs/03_Solution/architecture/DEVELOPER_REFERENCE_GUIDE.md` is a companion per-module "which
doc to read before coding" matrix across the REF→AUTH→GOV→REQ→SOLUTION→CODE chain. Treat
everything in this "Architecture" section above as the current CODE-layer reality and the Tech
Stack Decisions doc as the approved target for what's not yet built — don't assume one from the
other.

**Pre-DDL architecture gates (all FROZEN):**
`docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md` (`IMPLEMENTATION-TIER-001`,
unified 0–13 build order across 22 modules) → `FK_DEPENDENCY_GRAPH.md` ("Gate 8" — physical FK
dependency graph across 86 frozen tables, topologically sorted into 8 depths with zero cycles,
resolves the audit-actor circular-dependency problem via a two-pass DDL strategy) →
`DDL_CREATION_ORDER.md` ("Gate 9" — the exact numbered `CREATE TABLE` sequence for all 86
tables plus the Pass-2 deferred-constraint list). Tiers 0-6 of the unified build order are
executed or in progress (see "Current position" above). **Tier numbering is now unified:**
`IMPLEMENTATION_DEPENDENCY_ORDER.md` has been restructured to the single agreed build-order
sequence — Bootstrap/RBAC (Tier 0), Foundation (1), Organization (2), Person (3), Family +
Membership (4), Authentication + Administration + Audit (5), Governance + Attendance + Assets &
Property (6), Heritage (7), Programmes & Events (8), Kumari/Kishor/Sevak (9), Mahila (10),
Publications + UPBS (11), Finance (12), Reports + Backup & Technical (13). This resolves the
former divergence in which the dependency doc bundled Person + Organization at "Tier 2" and
reserved "Tier 3" for Heritage: "Tier 2" now means Organization and "Tier 3" means Person
consistently across every doc (`CLAUDE.md`, the code-explanation docs, `docs/03_Solution/api/`).

**`BOOTSTRAP_ARCHITECTURE.md`** (`SOL-ARCH-011`, FROZEN) defines a "Phase 0" that sits *before*
Tier 1: `role_master`/`permission_master`/`role_permission` have zero FK dependencies, so they
are created and seeded before Foundation — resolving the same audit-actor circular dependency
via the same two-pass strategy. It establishes `nss_db_owner` (PostgreSQL DDL owner) as
distinct from `NSS_ERP_ADMIN` (an ERP RBAC role, a `role_master` row) — the two are explicitly not
equivalent, and `NSS_ERP_ADMIN` never bypasses RBAC checks. DDL for all 3 tables exists under
`database/ddl/00_bootstrap/` and is **implemented and committed** (`feat(bootstrap): Phase 0
Bootstrap RBAC DDL and seed data`); seed data is now complete (`role_master`: 10 roles;
`permission_master`/`role_permission`: **now populated in Tier 5, in progress** —
`FOUNDATION_VIEW`/`ORGANIZATION_VIEW`/`PERSON_VIEW`/`PERSON_VIEW_SENSITIVE`/`FAMILY_VIEW`/
`MEMBERSHIP_VIEW`/`AUDIT_VIEW` plus the admin/user-management permission set are mapped to
roles — the "empty, pending the permission catalogue" state below no longer applies). Ownership of
the 3 tables remains with Administration — "Bootstrap" is a DDL-sequencing label, not a new
module (see Gotchas).

## Tier-wise Implementation Plan

The system is built **vertically by tier**: each tier completes DB → API → UI before the
next tier begins. This is distinct from the DDL depth order (which is an internal database
concern within each tier's DB phase).

**Authority:** `docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md`
(`SOL-ARCH-008`, `IMPLEMENTATION-TIER-001`)

### Tier sequence

| Tier | Modules | Focus |
|-----:|---------|-------|
| 0 | Bootstrap | PostgreSQL bootstrap (database, roles, extensions, `nss` schema) + initial RBAC tables |
| 1 | Foundation | Common master/reference infrastructure (master_data, geography, sequences, settings) |
| 2 | Organization | Organizational hierarchy (Kendra → Anchalika/Zilla → Sakha) |
| 3 | Person | People identity (Sangha Sevi ID) |
| 4 | Family + Membership | Family groups, membership types (Probationary/Regular/Associate), Sakha affiliation, local IDs, transfer |
| 5 | Authentication + Administration + Audit | User accounts, RBAC enforcement, organizational scopes, audit trail |
| 6 | Governance + Attendance + Assets & Property | Governance positions, Sangha Puja attendance, immovable/movable property |
| 7 | Heritage | Founder biography, teachings, objectives, historical milestones, office bearers |
| 8 | Programmes & Events | Event types, instances, sessions, registration (Janmotsaba, Rasoutsaba, etc.) |
| 9 | Kumari + Kishor + Sevak | Youth/seva participation domains (Kumari/Kishor IDs, Seva architecture, Dina-Lipi, Niyam Panchak) |
| 10 | Mahila | Mahila-specific operations (not a separate membership category — Mahila Puja is Sangha Puja with majority women) |
| 11 | Publications + UPBS | Publication catalogue/operations, UPBS operational integration |
| 12 | Finance | Financial transactions (Pranami, event fees, publication sales, property income) — deliberately late, references upstream domains |
| 13 | Reports + Backup & Technical | Reporting, analytics, backup/restore, technical administration |

### Vertical slice per tier

Each tier follows the same internal sequence:

```
Database
  ├── Review frozen table design
  ├── DDL (CREATE TABLE in dependency-depth order)
  ├── Constraints + indexes
  ├── Seed data
  └── DB validation
       │
       ▼
API
  ├── Design + schemas
  ├── Endpoints
  └── Authorization
       │
       ▼
UI
  ├── Pages + forms
  ├── Tables + lists
  └── API integration
       │
       ▼
Integration test → freeze tier → next tier
```

### Key architectural facts per tier

**Tier 0 (Bootstrap):** PostgreSQL `nss_db_owner` role (database-level DDL owner) is distinct
from ERP `NSS_ERP_ADMIN` role (application RBAC row in `role_master`). Bootstrap RBAC tables
(`role_master`, `permission_master`, `role_permission`) are owned by the Administration
module — "Bootstrap" is a DDL-sequencing label, not a new module. Permission catalogue is
not yet frozen.

**Tier 0 — RBAC role model (frozen):** The 8 frozen ERP roles (3 SYSTEM + 5 ORGANIZATIONAL)
are **parallel entries in `role_master`** — there is no role hierarchy or inheritance. A user
may hold **multiple roles simultaneously** (`user_role` is a junction table, 1:N from
`user_account`, N:1 to `role_master`). Scope attaches to the **role assignment** (via
`admin_scope`), not to the person globally — the same person can therefore hold different
roles with different organizational scopes. Governance position (President, Secretary, etc.)
is never used as a permission mechanism; role assignment is explicit and independent.
`NSS_ERP_ADMIN` and the 5 organizational admin roles (`NSS_ERP_KENDRA_ADMIN`,
`NSS_ERP_ANCHALIKA_ADMIN`, `NSS_ERP_ZILLA_ADMIN`, `NSS_ERP_SAKHA_ADMIN`,
`NSS_ERP_PATHA_CHAKRA_ADMIN`) initially share the same permission set — the only distinction is
scope, not permissions; each organizational role is never a prerequisite for, and never
automatically grants, another. Eligibility differs per role: `NSS_ERP_ADMIN` may go to any NSS
member with a valid Parichay Patra when system-wide administration is authorized (Governing Body
membership is not required); each organizational role typically goes to that unit's Governing
Body members or another authorized individual (`05_administration_table_design.md` §8.11, v1.2.0).
The Administration UI may present
a **composite administrative view** joining member identity, governance, roles, scope, and
organization — this is a read-model / presentation concern, never a denormalized table
(SOL-ADMIN-001 §63).

**Implementation principle — cross-platform wrappers (frozen):** The SQL DDL, seed data,
FastAPI application, and UI are **identical across platforms**. `.sh` (macOS/Linux) and `.ps1`
(Windows) scripts are developer/operational wrappers only — they must not contain different
business logic, database statements, or schema definitions. Platform-specific behaviour is
limited to shell mechanics (variable substitution, exit codes, colour output).

**Tier 2-3 (Organization + Person):** Person is the central human identity. The global Sangha
Sevi ID (e.g. `SS1`) is permanent, unique across NSS, never changes, never reused.
Organization hierarchy: Kendra → Anchalika/Zilla → Sakha → Sakha Asana → Patha Chakra.
Nilachala Kutira and Smruti Mandira are separate roots, not children of Kendra. Organization
stores location inline (country, city_village, postal_code FKs + lat/long), no separate
`organization_address` table.

**Tier 4 (Family + Membership):** Membership is not the same as Sakha affiliation.
`membership_sakha_affiliation` carries effective-dated Sakha assignment. Transfer: old local
ID archived, new local ID issued, global Sangha Sevi ID unchanged. Local ID format:
`<3-5 char org code><sequence>` (e.g. `ESS123`).

**Tier 5 (Auth + Admin + Audit):** Effective access = User + Role + Permission +
Organizational Scope. Audit is separate from change history — `field_change_log` (Foundation)
handles field-level change tracking; `audit_master`/`system_event_log` were the two tables
*planned* for security/system events in the design docs (`docs/03_Solution/modules/audit/`), but
only `nss.system_event_log` has actually shipped as DDL so far (`database/ddl/01_foundation/
14_system_event_log.sql`, populated by both a DB-level `fn_audit_trigger()` (which also writes field-level rows to
`field_change_log`, AUDIT-ARCH-001) and the app-level `api/helpers.py::log_audit()` — plain CRUD
yields duplicate `system_event_log` rows of different shape, an accepted trade-off, see Gotchas);
`audit_master` remains design-only, not built.

**Tier 6 (Attendance):** Membership Sakha ≠ Attendance Sakha. A member affiliated with
Sakha A can attend Sangha at Sakha B — the attendance record identifies the actual Sakha
where attendance occurred. Weekly Sangha Puja is owned by Attendance, not Programme & Events.
Attendance types: REGULAR, DARSHAK, VISITOR.

**Tier 6 (Assets & Property):** Legal owner, registered holder, and custodian are distinct
concepts. Covers acquisition, disposal, custody, maintenance, valuation, depreciation,
insurance, statutory obligations, restricted property.

**Tier 8 (Programme & Events):** Common structure: Programme Type → Event → Event Instance
→ Event Day → Event Session, plus Registration. Finance owns actual event financial
transactions. Attendance remains Attendance-owned.

**Tier 9 (Kumari/Kishor/Sevak):** These are not adult Membership categories. Kumari and
Kishor have separate identity/participation domains. Sevak architecture: Seva → Seva Head →
Application → Recommendation → Approval. Guardian model for minors includes
`guardian_sangha_sevi_pk`.

**Tier 12 (Finance):** Financial year 1 April – 31 March. Finance owns all actual
transactions. Other modules reference Finance — they do not create competing transaction
ledgers.

### Current position

Tiers 0-5 (Bootstrap, Foundation, Organization, Person, Family + Membership, Authentication +
Administration) are all **implemented**; the latest release is **v0.11.0**. (The notes below were
written tier-by-tier; Tier 5 detail is under Architecture.) Tier 0-4 DB phases:  `database/ddl/03_person/02_person.sql`
(`person`, 28 columns) and `03_person_address.sql` (`person_address`) are real, implemented DDL
— following the same
Foundation `master_data` pattern as Organization (gender/marital_status/blood_group/
address_type resolve through `master_data`, not dedicated per-domain master tables). Only
`01_person_master_tables.sql` (the original per-domain gender/marital_status/address_type
master tables) remains superseded — its data now lives in Foundation's `master_data` seed.
`database/ddl/04_family/` (5 tables: `family_group`, `family_relationship`,
`family_head_history`, `family_transition_history`, `family_link` — the last stores only
direct `PARENT_OF`/`SPOUSE_OF` edges between two persons; every other kinship term is computed
dynamically via BFS graph traversal, see Key Workflow #6) and `database/ddl/05_membership/` (12
tables: `sangha_sevi` plus status/renewal/transfer/affiliation/journey/review history tables,
`parichaya_patra`/`anumati_patra` and their history tables) are both real, implemented DDL too.
Tier 0's API phase is **implemented** (4 read-only bootstrap-RBAC endpoints in
`api/routers/bootstrap.py`). Tier 1's API phase (Foundation) is **implemented** — 17 read-only
endpoints across 11 tables in `api/routers/foundation.py`, with a matching Foundation
Verification UI (`frontend/foundation.html`) and 59 pytest integration tests — merged to `main`
and tagged as v0.7.0. Tier 2's API phase (Organization) is **implemented** — 7 read-only
endpoints (reference data, organizations list/detail/children with `limit`/`offset` pagination,
a `/children-stats` aggregate-counts endpoint added on top of Tier 4 (see Key Workflow #6),
a recursive-CTE `/hierarchy`, also paginated) in `api/routers/organization.py`, with a matching
Organization Verification UI (`frontend/organization.html`) — merged to `main` and tagged as
v0.8.0 (the 7th endpoint, `/children-stats`, landed later as part of the Tier 4 work and is
committed, not a later addition). Tier 3's API phase (Person) is **implemented and released** — 4 read-only
endpoints (`/persons` list with gender/marital-status/blood-group filters + pagination,
`/persons/{person_pk}` detail, `/persons/{person_pk}/addresses`, `/search?q=` pg_trgm fuzzy
search) in `api/routers/person.py`, a matching Person Verification UI (`frontend/person.html`)
— merged to `main` and tagged as v0.9.0, alongside the Organization master-data migration (see
Key Workflow #4). Tier 4's API phase (Family + Membership) is **implemented and released**
— 7 read-only Family endpoints (`api/routers/family.py`: `/families` list, detail, members,
head history, plus `/graph`, `/sakha-alignment`, `/person/{pk}/membership-summary` — see Key
Workflow #6) and 7 read-only Membership endpoints (`api/routers/membership.py`: `/members`
list, detail, `/search` (7-field), Sakha affiliation history, Parichaya Patra, Anumati Patra,
journey-event timeline — see Key Workflow #6), each with a matching Verification UI
(`frontend/family.html`, `frontend/membership.html`). This work was merged to `main` and tagged
as **v0.10.0**, followed by three hotfix tags — **v0.10.1** (wired `family_link` into the build
scripts, extended `render_build.sh` through Tier 4), **v0.10.2** (Neon role-creation-order fix —
creates `nss_db_owner`/`nss_db_backend` before granting), and **v0.10.3** (idempotent DDL
`CREATE TABLE`/`INDEX` plus idempotent seed `INSERT`s, root-causing a Neon schema/data drift
bug) — see Gotchas for detail on each. A performance-hardening pass on top of this (query
indexes, connection-pool sizing, non-blocking frontend fetches) was released as **v0.10.4**,
merged from branch `performance-optimization`. A combined 410
pytest integration tests now exist across all five tiers (21 bootstrap + 59 foundation + 72
organization + 61 person + 8 security + 67 family + 99 membership + 23 cross-module integrity);
one,
`test_kumari_transition_has_event`,
currently fails (see Conventions & Gotchas). **(Pre-Tier-5 baseline — on the in-progress branch
below, this test now `pytest.skip()`s instead of failing.)** All
other API phases and all other UI phases remain **unimplemented** across the remaining tiers.

**Note on the Tier 0-4 Verification UI file names above:** `index.html`, `foundation.html`,
`organization.html`, `person.html`, `family.html` and `membership.html` are named here as the UI
each tier *shipped with*; all six have since been **deleted from disk** and their functionality
folded into `admin.html` (Bootstrap RBAC → System Settings; Foundation → Reference Data +
Geography; Organization → Organizations + Organization Hierarchy; Person → Person Directory;
Membership → Member Directory) and `dashboard.html` (Family → Family tab; Membership →
Membership tab). See the `frontend/` directory-structure section below.

**Tier 5 (Authentication + Administration) DB/API/UI phases are complete and released
as `v0.11.0`** (merged to `main`; the tag exists locally, not yet pushed). See the "Tier 5" subsection under Architecture above for the
full detail (new tables, routers, services, dependencies, removed seed data, and the new
session-scoped test-fixture architecture). The suite was not executed as part of cutting the release (see
`docs/05_Releases/v0.11.0.md`); run `pytest -m integration` against a bootstrapped DB before relying on it.

### Database schema

All application tables live in the `nss` schema (`CREATE SCHEMA nss`). The `public` schema
is reserved for PostgreSQL extensions (pgcrypto, pg_trgm, btree_gin, postgis). The database
default `search_path` is set to `nss, public`. All DDL uses explicit `nss.` prefix on table
names, FK references, and index targets.

## Directory structure

```
NSS_ERP/
├── api/                          FastAPI application — 15 routers (Tier 0-4 read routers plus Tier 5
│                                   auth/admin/registration/claim_approval/audit/geo_approval),
│                                   `services/`, `dependencies/`, `schemas/` layers, see below
├── frontend/                      Four Tier 5 pages (`login`/`register`/`dashboard`/`admin` .html)
│                                   + `assets/`, served as static files by FastAPI (see below)
├── database/
│   ├── ddl/                     Hand-written PostgreSQL schema, numbered by module (adds
│   │                             06_authentication/, 07_administration/ — Tier 5, see above)
│   ├── seed/                    Reference/lookup data matching the DDL (Tier 4 demo/
│   │                             verification seed files removed in Tier 5 — see
│   │                             above; new 04_admin/ folder seeds a single admin superuser)
│   ├── migrations/              REMOVED in Tier 5 — see above
│   │                             (its narrow `fixes/` successor, added on this same branch to
│   │                             hold one-off data-repair scripts, has since been deleted too —
│   │                             its only file was verified obsolete against `family.py`'s
│   │                             auto-transfer logic and the now-deleted demo seed data it
│   │                             targeted; there is no `database/fixes/` folder anymore)
│   └── scripts/                 Executable bootstrap/build/validate/grant scripts (see below;
│                                 gains `05_create_writer_role.sql`/`06_setup_env.sh` on the
│                                 Tier 5)
├── scripts/                      New top-level folder (Tier 5) — `bootstrap_admin.py`,
│                                   run by `02_build.sh`/`render_build.sh` Phase 13 to seed the
│                                   admin superuser with a runtime-generated Argon2 hash
├── tests/                        pytest suite, reorganized (Tier 5) into
│                                   tests/api/ (17 files, one per router/concern incl.
│                                   test_geo_approval.py), tests/db/ (test_data_integrity.py,
│                                   test_credential_schema.py, test_festival_schema.py),
│                                   tests/security/ (7 files), tests/ui/ (23 Playwright
│                                   browser-test files), and conftest.py at the package root —
│                                   see Setup & running and `tests/README.md` for the current
│                                   per-file breakdown
├── docs/
│   ├── PROJECT_DOCUMENTATION.md This file
│   ├── 00_Project_Governance/   AUTH/ GOV/ GDR/ STD/ — governance framework + engineering standards
│   ├── 01_Authoritative_References/
│   │   ├── NSS/            Source-faithful transcription of NSS's Constitution & Bye-Laws (see detail below)
│   │   └── MAHILA_SANGHA/  Source-faithful transcription of Mahila Sangha's own Bye-Law (see detail below)
│   ├── 03_Solution/             Per-module design docs — 22 module folders (organization,
│   │                            person, membership, family, attendance, heritage, kumari,
│   │                            kishor, mahila, sevak, foundation, administration,
│   │                            authentication, governance, publications, reports, upbs,
│   │                            audit, backup_technical, finance, programmes_events,
│   │                            assets_property) + architecture/ui/infrastructure/standards/
│   │                            database/security/code_explanations content populated (see
│   │                            detail below); `docs/03_Solution/api/` now holds 4 per-tier
│   │                            API contract docs (Bootstrap/Foundation/Organization/Person —
│   │                            consolidated here, moved out of `architecture/`) plus a new
│   │                            cross-tier `API_CONTRACT.md` (Tiers 0-4, no dedicated
│   │                            per-tier doc for Family/Membership; see detail
│   │                            below), distinct from the real, implemented root-level `api/`
│   │                            code folder
│   └── 05_Releases/             Release notes, v0.1.0 → v0.11.0
├── BY-LAW/                       Original source PDFs/docx of the NSS and Mahila Sangha Bye-Laws — the primary source both `docs/01_Authoritative_References/NSS/` and `.../MAHILA_SANGHA/` are transcribed from
├── render.yaml                    Render.com Infrastructure-as-Code — free-tier web service
│                                   (`uvicorn api.main:app`); does not provision a database — DB
│                                   env vars point to an externally-managed Neon.dev instance
├── render_build.sh                 Render build hook — installs deps; existence-gated DB
│                                   bootstrap every deploy; truthy `RUN_DB_BOOTSTRAP` gates only
│                                   the Phase 13 admin seed
├── requirements.txt              Python dependencies (pip, not pinned to a venv tool)
├── package.json / tailwind.config.js  Tailwind CLI + DaisyUI build tooling only (`npm run css:build`/`css:watch`)
├── pytest.ini                     pytest config — `testpaths = tests`; `integration`/`ui`/`db` markers
├── CLAUDE.md                     AI-agent operating memory/context (terse, instruction-oriented)
├── NSS LOGO/                     Source logo artwork (web copy: frontend/assets/img/nss-logo.png)
└── README.md                     Project pitch / high-level status
```

`database/scripts/` holds the executable bootstrap/build/validate/grant scripts
(`00_create_database.sql`, `01_extensions.sql`, `02_build.sh`/`.ps1`, `03_validate.sh`/`.ps1`,
`04_grant_backend.sql`, `05_create_writer_role.sql`, `06_setup_env.sh`) that replaced the old repo-root `validate_foundation.sh` (deleted) — see
the `database/` detail below.

### `api/` — FastAPI application detail

```
api/
├── main.py             FastAPI app entry point — builds `app`, registers the security
│                       middleware stack (rate limiting, opt-in CORS, security headers — see
│                       Architecture above), includes all routers, mounts
│                       `frontend/assets/` at `/assets`, 302-redirects `/` to `/login`, and
│                       serves `frontend/login.html` at `/login`,
│                       `frontend/register.html` at `/register`,
│                       `frontend/dashboard.html` at `/dashboard`, and
│                       `frontend/admin.html` at `/admin` (all skipped
│                       if the
│                       respective file/dir doesn't exist — API-only mode still works). The six
│                       original Tier 0-4 page routes (`/`→`index.html`, `/foundation`,
│                       `/organization`, `/person`, `/family`, `/membership`) were deleted with
│                       their pages — see the "Retired standalone verification pages" comment in
│                       the file. Disables
│                       `/docs`/`/redoc`/`/openapi.json` if `DISABLE_DOCS` is set, closes the DB
│                       pool on shutdown. Run with:
│                       `python3 -m uvicorn api.main:app --reload --port 8001` (from repo root)
├── config.py           Settings: DB_NAME/DB_USER/DB_PASSWORD (required), DB_HOST (default
│                       localhost), DB_PORT (default 5432), API_PORT (default 8001),
│                       DISABLE_DOCS (default false), CORS_ORIGINS (comma-separated, default
│                       empty ⇒ CORS middleware not registered), RATE_LIMIT (default
│                       `60/minute`) — read from `api/.env` via python-dotenv;
│                       `Settings.validate()` raises if any required var is missing
├── database.py         psycopg2 `ThreadedConnectionPool` — read pool 2-15 conns as `nss_db_backend` plus a write pool 1-5 conns as `nss_db_writer` (`get_write_connection`)
│                       (read-only); `get_connection()` is a FastAPI generator dependency;
│                       `check_connection()` backs the /health endpoint
├── middleware.py       `add_security_headers(request, call_next)` — sets
│                       `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`/
│                       `Permissions-Policy` on every response, plus `Cache-Control: no-store`
│                       scoped to `/api/*` only; registered in `main.py` via
│                       `app.middleware("http")`
├── helpers.py          Shared cursor→Pydantic conversion (`rows_to_models`, `row_to_model`) and
│                       pagination constants (`DEFAULT_LIMIT = 100`, `MAX_LIMIT = 500`) used by
│                       every router — extracted from per-router duplicates when Tier 3 (Person)
│                       landed so limit/offset validation stays consistent everywhere
├── routers/
│   ├── bootstrap.py    4 endpoints under `/api/v1/bootstrap` — no auth, no ORM, raw
│   │                   parameterized SQL against `nss.role_master`/`permission_master`/
│   │                   `role_permission` (see Key workflows below)
│   ├── foundation.py   33 endpoints under `/api/v1/foundation` — 21 reads (17 original plus
│   │                   `/post-offices`, `/sakha-postal-codes`, `/festivals`, `/festival-calendar-dates`) and 12
│   │                   writes (6 `FOUNDATION_MANAGE` plus festival-calendar `POST`/`PATCH` gated by
│   │                   `FOUNDATION_CALENDAR_MANAGE`, NSS_ERP_ADMIN only, plus 4 member-facing
│   │                   `POST /{districts|postal-codes|post-offices|city-villages}/propose`): master data (`/categories`,
│   │                   `/master-data` — now also `POST`/`PATCH`), system config (`/settings`,
│   │                   `/sequences` — both now also `POST`/`PATCH`),
│   │                   geography (`/countries`→`/states`→`/districts`→`/cities`,
│   │                   `/postal-codes`, `/postal-code-mappings`), runtime (`/documents`); all
│   │                   reads gated by `require_permission("FOUNDATION_VIEW")`, all 6 writes by
│   │                   `require_permission("FOUNDATION_MANAGE")` (Tier 5) — see
│   │                   `api/routers/foundation.py::create_master_data`/`update_master_data`/
│   │                   `update_setting`/`create_setting`/`update_sequence`/`create_sequence`.
│   │                   `field_change_log` deliberately not exposed here — see the dedicated
│   │                   `AUDIT_VIEW`-gated `audit.py` router instead; see Key workflows below and
│   │                   `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` (v1.2 — documents the
│   │                   permission gate and the 6 write endpoints)
│   ├── organization.py 11 endpoints (8 original plus `/organizations/selectable` [login-only], `/organizations/{pk}/wings`, `/wings/{wing_type_code}/members`) under `/api/v1/organization` across `nss.organization` plus
│   │                   Foundation's `master_data` — reference (`/types`, `/statuses`, both
│   │                   querying `master_data` filtered by `master_category.category_code`
│   │                   `ORGANIZATION_TYPE`/`STATUS` — 13 types, incl. Tier 4's
│   │                   `KUMARI_SANGHA`/`SEVAK_SANGHA`/`MAHILA_SANGHA`; `/statuses` additionally
│   │                   filters by the new `applicable_modules` column, Tier 4, so it returns 7
│   │                   of the category's 16 total values, not all of them), core
│   │                   (`/organizations` with optional `type_code`/`status_code` filters plus
│   │                   `limit`/`offset` pagination, `/organizations/{organization_pk}`,
│   │                   `/organizations/{organization_pk}/children`), two aggregate-stats
│   │                   endpoints — `/organizations/{organization_pk}/children-stats` (per-child
│   │                   family/member/person counts via a recursive CTE that also applies the
│   │                   FAM-036 majority-rule "effective Sakha" computation — this CTE has no
│   │                   depth-cap guard, unlike `/hierarchy` below, a real unresolved gap; see
│   │                   Gotchas) and a newer `/organizations/{organization_pk}/stats`
│   │                   (v0.11.0); both share the FAM-036
│   │                   CTE via a single `FAMILY_MAJORITY_CTE_SQL` constant in `api/helpers.py`
│   │                   (Tier 5) rather than a duplicated copy — see Key Workflow #4 — and the
│   │                   self-referencing tree (`/hierarchy`,
│   │                   a `WITH RECURSIVE org_tree` CTE returning a flat depth-annotated list,
│   │                   also paginated, **with** a depth-cap guard); all organization-shaped endpoints share one SQL
│   │                   fragment (`_ORG_SELECT`) that LEFT JOINs the self-referencing parent plus
│   │                   Foundation's district/state/country/city_village/postal_code tables; see
│   │                   Key workflows below and
│   │                   `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` (documents the
│   │                   original 7, not yet updated for `/stats`)
│   ├── person.py       5 endpoints (incl. login-only `/search-selectable`) under `/api/v1/person` across `nss.person` +
│   │                   `nss.person_address` plus Foundation's `master_data` — core (`/persons`
│   │                   list with optional `gender_code`/`marital_status_code`/
│   │                   `blood_group_code` filters + `limit`/`offset` pagination,
│   │                   `/persons/{person_pk}` detail), addresses
│   │                   (`/persons/{person_pk}/addresses`, 404 if the person doesn't exist),
│   │                   search (`/search?q=` — `pg_trgm` similarity (0.45 threshold) on
│   │                   `first_name`/`last_name`, email-shaped queries split on `.`/`@` first,
│   │                   plus `ILIKE` prefix match on `person_id`/`mobile_number`/`email`, ordered
│   │                   by similarity, capped at 50 results); `aadhaar_encrypted`/`aadhaar_hash` are
│   │                   never returned (PER-BR-081) — only `aadhaar_last4` is exposed for masked
│   │                   display; see `docs/03_Solution/api/PERSON_API_CONTRACT.md`
│   ├── family.py       Originally 7 endpoints under `/api/v1/family` across all 5 Family
│   │                   tables — `/families` list (filters + pagination),
│   │                   `/families/{family_pk}` detail, family members (relationships per
│   │                   family), family head history per family, plus 3 newer endpoints:
│   │                   `/families/{family_pk}/graph?viewer_person_pk=`
│   │                   (dynamic relationship-label computation via BFS traversal over
│   │                   `nss.family_link` edges, delegated to `api/services/family_graph.py` —
│   │                   **no test coverage**), `/families/{family_pk}/sakha-alignment` (FAM-036
│   │                   majority-rule "effective Sakha", with `is_aligned` hardcoded `True` by
│   │                   design since the returned Sakha is always the computed majority — see
│   │                   Key Workflow #6), and `/person/{person_pk}/membership-summary` (bridges
│   │                   family context to membership context — **no test coverage**); no
│   │                   dedicated per-tier contract doc — documented in the
│   │                   consolidated `docs/03_Solution/api/API_CONTRACT.md` instead (see Key
│   │                   workflows below). **On the in-progress Tier 5 (Tier 5),
│   │                   this router gained 9 more, authenticated write endpoints — `POST
│   │                   /families` (create), `POST`/`DELETE /families/{pk}/members` (add/remove
│   │                   member), `POST /families/{pk}/links`, `GET/POST/DELETE
│   │                   /families/{pk}/admins` (family_admin CRUD), `POST
│   │                   /families/{pk}/transfer-head`, and `GET /person/{pk}/families` — 16
│   │                   endpoints total; the 9 new ones are covered by `tests/api/test_family_ownership.py`. The module's own
│   │                   docstring was updated accordingly ("Tier 4 read-only + Tier 5 write
│   │                   endpoints") — no longer stale, correcting an earlier revision of this
│   │                   file that said otherwise.**
│   └── membership.py   8 endpoints under `/api/v1/membership` across all 14 Membership tables
│                       plus `nss.person`/`nss.organization` — core (`/members` list with
│                       filters + pagination, `/members/{member_pk}` detail), search (`/search`
│                       — 7-field: `sangha_sevi_id`, `person_id`, `local_sakha_erp_id`, name
│                       trigram (threshold 0.45), mobile, email, Kendra number; plus a 4-field
│                       person search using the same trigram threshold and email-split rule) —
│                       list/detail/search are gated by `require_permission("MEMBERSHIP_VIEW")`;
│                       Sakha affiliation history, Parichaya Patra records, Anumati Patra
│                       records, and a journey-event timeline (all per member) instead use an
│                       **ownership model** (v0.11.0)`/`require_self_or_permission()` helper) —
│                       `get_current_user` plus either `MEMBERSHIP_VIEW` or being the member
│                       themself. An 8th endpoint,
│                       `/organizations/{organization_pk}/darshak-summary` (Tier 5,
│                       `MEMBERSHIP_VIEW`-gated), returns
│                       `home_probationary_count`/`attending_from_other_sakha_count` for an org's
│                       own Darshak dashboard card, backing the new Org Dashboard tab (see
│                       Frontend detail below). Implements the
│                       three-tier member identity model (Sangha Sevi ID / Local Sakha Number /
│                       Kendra Number — see Key workflows below); trigram search on email-shaped
│                       queries splits on `.`/`@` (`re.split(r'[.@]', q)[0]`) before computing
│                       similarity, to avoid false positives from long literal strings; no
│                       dedicated per-tier contract doc — documented in the consolidated
│                       `docs/03_Solution/api/API_CONTRACT.md` instead (documents the original 7,
│                       not yet updated for `/darshak-summary` or the ownership-model change)
├── services/           New layer (Tier 4), distinct from `routers`/`schemas` — pure Python
│   └── family_graph.py business logic with no direct DB access. Builds an in-memory graph from
│                       `family_link` rows (`build_family_graph()`), then computes relationship
│                       labels relative to any viewer via BFS over `UP`/`DOWN`/`SPOUSE` steps
│                       (`compute_relationships()`), using a `PATH_LABELS` lookup table keyed by
│                       step-tuples with gendered (male_label, female_label) pairs — e.g.
│                       `(Step.UP, Step.UP)` → ("Grandfather", "Grandmother"). Called by
│                       `api/routers/family.py`'s `/graph` endpoint.
└── schemas/
    ├── bootstrap.py    Pydantic response models (RoleResponse, PermissionResponse,
    │                    HealthResponse); audit columns deliberately excluded from the contract
    ├── foundation.py   11 plain Pydantic models (no `from_attributes`, raw psycopg2 dicts) —
    │                    one per exposed table/view; excludes audit columns plus
    │                    `current_value` (sequences) and unimplemented FK columns (documents)
    ├── organization.py 5 plain Pydantic models (no `from_attributes`, raw psycopg2 dicts) —
    │                    OrganizationTypeResponse, StatusResponse (renamed from
    │                    `OrganizationStatusResponse` now that it backs the unified,
    │                    cross-module `STATUS` master-data category rather than an
    │                    organization-only status table),
    │                    OrganizationResponse (full contact/online-presence fields — nullable
    │                    `phone_number`/`mobile_number`/`org_email`/`org_website_url`/
    │                    `org_youtube_channel_url`; required `email`/`website_url`/
    │                    `youtube_channel_url` with NSS-wide DB defaults — plus resolved
    │                    type/status/parent names and Foundation geography names),
    │                    OrganizationHierarchyNodeResponse (leaner, no contact/geography fields,
    │                    matching `/hierarchy`'s narrower SQL), OrgChildStatsResponse (per-child
    │                    family/member/person counts, backing `/children-stats`); excludes audit columns
    ├── person.py       3 plain Pydantic models (no `from_attributes`, raw psycopg2 dicts) —
    │                    PersonResponse (full detail: demographics + resolved gender/
    │                    marital_status/blood_group/emergency_relationship names, masked
    │                    `aadhaar_last4` only, photo FK), PersonSummaryResponse (list/search —
    │                    omits Aadhaar, emergency contact, photo), PersonAddressResponse
    │                    (resolved address_type plus city_village/postal_code/district/state/
    │                    country chain via the `city_village_postal_code_map` junction);
    │                    excludes audit columns
    ├── family.py       8 plain Pydantic models — FamilyGroupResponse, FamilyMemberResponse
    │                    (gained an `is_head` field), FamilyHeadHistoryResponse, plus 5 newer
    │                    models backing the graph/alignment endpoints:
    │                    FamilyGraphMemberResponse (adds `relationship_label`/`generation`/
    │                    `spouse_person_pk`/`parent_person_pks` on top of the base person
    │                    fields), PersonMembershipSummaryResponse, SakhaAffiliationCount,
    │                    MemberSakhaInfo, FamilySakhaAlignmentResponse (`is_aligned` hardcoded
    │                    `True`); excludes audit columns
    └── membership.py   5 plain Pydantic models — MemberResponse, SakhaAffiliationResponse,
                         ParichayaPatraResponse, AnumatiPatraResponse, JourneyEventResponse;
                         excludes audit columns
```

This is the only API layer in the codebase. `backend/` (the earlier Django prototype
covering `foundation`, `authentication`, `family`, `membership`, `heritage`) was fully archived
and removed once the FastAPI direction was adopted; the directory is now empty — Family and
Membership's current implementations under `api/routers/`/`api/schemas/` are an unrelated,
from-scratch FastAPI rebuild, not a revival of any Django-era code. Modules
referenced elsewhere in the project's roadmap (`mahila`, `kumari`, `kishor`, `sevak`,
`publications`, `upbs`, `reports`) **do not exist yet** in either `api/` or
any other code form — they are planned, not scaffolded.

### Tier 5 (Authentication + Administration) — released in v0.11.0

**Not yet merged to `develop`/`main`, not yet released.** The working tree on this branch adds a
full read-write vertical slice on top of the read-only Tiers 0-4 above. Treat everything in this
subsection as in-flight, not a frozen/shipped feature — verify against `git status`/`git log`
before assuming any of it is final.

```
api/
├── config.py            + JWT_SECRET_KEY/JWT_ALGORITHM(HS256)/JWT_ACCESS_TOKEN_MINUTES(30)/
│                          JWT_REFRESH_TOKEN_DAYS(7)/JWT_ABSOLUTE_SESSION_DAYS(30),
│                          DB_WRITE_USER/DB_WRITE_PASSWORD + DB_READ_POOL_MIN/MAX,
│                          DB_WRITE_POOL_MIN/MAX, MAX_FAILED_ATTEMPTS(5)/
│                          LOCKOUT_DURATION_SECONDS(30), PASSWORD_MIN/MAX_LENGTH(8/128)/
│                          PASSWORD_EXPIRY_DAYS(365)/PASSWORD_EXPIRY_WARNING_DAYS(30),
│                          RESET_OTP_LENGTH(6)/RESET_OTP_EXPIRY_MINUTES(15)/
│                          RESET_OTP_MAX_ATTEMPTS(3)/RESET_OTP_RATE_LIMIT_MINUTES(60),
│                          DEBUG_MODE; `Settings.validate_auth()` raises if JWT_SECRET_KEY/
│                          DB_WRITE_USER/DB_WRITE_PASSWORD are missing (only called by
│                          `get_write_pool()`, so read-only endpoints still work without them)
├── database.py          + a second connection pool: `get_write_pool()`/`get_write_connection()`
│                          connect as `nss_db_writer` (INSERT/UPDATE on auth+admin tables only,
│                          per `database/scripts/05_create_writer_role.sql`);
│                          `get_write_connection()` auto-commits on success, rolls back on any
│                          exception (unlike the read pool, which does neither)
├── helpers.py            + `next_id(cur, sequence_code)` (atomic `UPDATE ... RETURNING` against
│                          `id_sequence_master`, replaces the never-implemented Key Workflow #3
│                          gap for at least PERSON/SANGHA_SEVI/org-type sequences),
│                          `resolve_or_create_city_village()` (lookup-or-insert into
│                          `nss.city_village` by name+district, used by registration/admin org
│                          edits), `get_active_status_pk()` (STATUS/ACTIVE master_data_pk lookup),
│                          plus (Tier 5) 4 shared SQL fragment constants dedup-ing
│                          previously byte-identical router queries: `FAMILY_MAJORITY_CTE_SQL`
│                          (FAM-036, shared by `organization.py`/`family.py`),
│                          `ORGANIZATION_ADDRESS_JOINS_SQL` (shared by `organization.py`/
│                          `admin.py`), `PERSON_MASTER_DATA_JOINS_SQL` (shared by `person.py`'s
│                          own DETAIL/SUMMARY/COUNT selects), `MEMBER_JOINS_SQL` (shared by
│                          `membership.py`'s SELECT/COUNT)
├── dependencies/         New layer — FastAPI `Depends()` factories, distinct from services/
│   ├── auth.py           `get_current_user()` (mandatory — decodes the Bearer JWT, loads
│   │                     `UserContext` via `rbac_service.load_user_context()`, 401 on any
│   │                     failure) and `get_optional_user()` (same but returns `None` instead of
│   │                     raising)
│   └── rbac.py           `require_permission(code)` / `require_any_permission(*codes)` —
│                         dependency factories that wrap `get_current_user()` and additionally
│                         403 if the resolved `UserContext` lacks the permission(s)
├── services/
│   ├── family_graph.py  (Tier 4, unchanged)
│   ├── auth_service.py  Argon2 password hashing/verification (`PasswordHasher()` default
│   │                    params), `validate_password_policy()` (8-128 chars, ≥1 uppercase, ≥1
│   │                    digit), JWT `create_access_token()`/`create_refresh_token()`/
│   │                    `decode_token()` (PyJWT, HS256; `decode_token()` also enforces the
│   │                    30-day absolute session max via a `session_start` claim carried through
│   │                    both token types), `is_account_locked()`/`calculate_lockout_until()`
│   │                    (5 attempts → 30s lockout)
│   └── rbac_service.py  `UserContext`/`ScopeInfo` dataclasses + `load_user_context(conn, pk)` —
│                        2 queries (permissions = union of every active role's
│                        `role_permission` rows; scopes = one `ScopeInfo` per active `user_role`
│                        with its `admin_scope` row). `UserContext.has_permission()`/
│                        `has_any_permission()`/`has_scope_for_org()`/`is_nss_wide()` are the
│                        RBAC decision points every protected endpoint relies on
├── routers/
│   ├── auth.py           `/api/v1/auth` — `POST /login` (login_id = Sangha Sevi ID or Person
│   │                     ID, case-insensitive; Argon2 verify; 5-attempt/30s lockout; issues
│   │                     access+refresh JWT), `POST /refresh`, `POST /logout` (revokes the
│   │                     caller's `user_session` row; client also discards tokens),
│   │                     `GET /sessions` / `DELETE /sessions/{session_pk}` (own active sessions),
│   │                     `POST /change-password` (self-service, requires current password +
│   │                     reuse check), `POST /forgot-password` (generates a 6-digit OTP hashed
│   │                     and stored in `password_reset_token`, rate-limited 3/hour; always
│   │                     returns the same generic message to prevent user enumeration; the OTP
│   │                     itself is only echoed back as `otp_debug` when `DEBUG_MODE=true`),
│   │                     `POST /reset-password` (OTP verification + policy check),
│   │                     `GET /me` (profile + permissions + scopes for the authenticated user),
│   │                     `PATCH /profile` (self-service profile edit)
│   ├── admin.py          `/api/v1/admin` — 28 endpoints (3 later additions: `GET`/`PATCH /persons/{pk}`, `PATCH /patra/{type}/{pk}/document-number`): user CRUD (`GET/POST /users`,
│   │                     `GET /users/{pk}`, `GET /persons/check-contact` advisory duplicate
│   │                     lookup, `GET /users/check-account/{person_pk}` (Tier 5 —
│   │                     usable/soft-deleted-login check for the Create User
│   │                     wizard's Step 3), `POST /users/{pk}/reset-password`,
│   │                     `PATCH /users/{pk}/status`, `DELETE /users/{pk}` soft-delete), role
│   │                     assignment (`GET/POST /users/{pk}/roles`,
│   │                     `DELETE /users/{pk}/roles/{user_role_pk}`), `POST /persons`
│   │                     (admin-created person, no account), sangha-sevi provisioning
│   │                     (`POST /sangha-sevi`, `GET /sangha-sevi/check/{person_pk}`,
│   │                     `POST /sangha-sevi/check-batch`,
│   │                     `GET /sangha-sevi/without-account` (v0.11.0)),
│   │                     `GET /dashboard-stats`, and
│   │                     organization management (`GET/POST /organizations`,
│   │                     `GET /organizations/kumari-sevak-sakha-options` (ORG-BR-101/102),
│   │                     `GET /sakha-scope-options` (ORG-BR-103), `GET
│   │                     /organizations/code-availability`, `GET /organizations/next-code`
│   │                     (sequence-driven preview), `PATCH /organizations/{pk}/short-code`,
│   │                     `PATCH /organizations/{pk}` — both subtree-aware (Tier 5,
│   │                     ADMIN-BR-076/077): `NSS_ERP_ADMIN`/NSS-WIDE edits any
│   │                     org, any other scoped admin edits only their own scope subtree,
│   │                     regardless of holding `ORGANIZATION_MANAGE` or only
│   │                     `ORGANIZATION_VIEW`. `short-code`'s gate was fixed (Tier 5) — used
│   │                     to require `ADMIN_USER_MANAGE` outright, wrongly blocking scoped org
│   │                     admins. `PATCH /organizations/{pk}` also gained a
│   │                     `parent_organization_pk` re-parenting field (Tier 5), validated
│   │                     against a module-level `_ALLOWED_PARENT_TYPES` map shared with
│   │                     `create_organization()` — backs a new "Assign Sakhas" admin tab (see
│   │                     Frontend detail below). The org-list query was also missing the
│   │                     NSS-wide `email`/`website_url`/`youtube_channel_url` columns (only had
│   │                     the nullable per-org `org_*` overrides) — fixed (Tier 5); the org
│   │                     detail view now shows both an "(NSS)" and, when set, an "(Own)" row for
│   │                     each of Email/Website/YouTube. `PATCH /users/{pk}/status` only changes
│   │                     `account_status` — it never creates a `sangha_sevi`; activating a
│   │                     `PENDING_APPROVAL` account 422s if a PENDING `registration_claim`
│   │                     exists or the person has no active `sangha_sevi`
│   ├── registration.py   `/api/v1/register` (12 public endpoints: `POST ""`, `/check-duplicate`, `/lookup-existing`, `/claim`, `/reference-data`, and `/countries`/`/states`/`/districts`/`/cities`/`/postal-codes`/`/post-offices`/`/sakhas` lookups) — `POST ""` (self-registration): always creates `person`, and
│   │                     `user_account(PENDING_APPROVAL)` + `registration_claim` in the same
│   │                     transaction **only when `has_membership` is true** (a membership-less
│   │                     registrant gets no account; the password is discarded). They can come
│   │                     back via `POST /lookup-existing` (person_id + DOB) and `POST /claim`,
│   │                     which creates the account + claim (shared check
│   │                     `_verify_existing_person_for_claim()`); **no `sangha_sevi`/`membership_sakha_affiliation` row is
│   │                     created at registration time** — those are created later, on claim
│   │                     approval. Local Sakha Number is required for non-Darshaka claims,
│   │                     optional for Darshaka (`PROBATIONARY`); not validated at registration
│   │                     (admin verifies on approval). Also `POST /check-duplicate` (JSON body, not query string, so PII stays out of access logs; pre-submit
│   │                     contact-uniqueness check), and (Tier 5) 4 more public,
│   │                     unauthenticated endpoints — `GET /reference-data` (bundles countries +
│   │                     4 master-data categories + the Sakha list into one call), `GET
│   │                     /states`/`/districts`/`/postal-codes` (location cascade) — each a thin
│   │                     wrapper over `foundation.py`'s/`organization.py`'s own shared query
│   │                     functions, fixing a regression where Tier 5's permission gating had
│   │                     silently emptied every dropdown on this public page.
│   └── claim_approval.py `/api/v1/admin/claims` — Sakha-admin review queue for
│                         `registration_claim` rows: `GET ""` (list, scoped to the admin's
│                         `admin_scope` orgs unless NSS-WIDE), `GET/PATCH /{pk}` (detail / admin
│                         edits before approval), `POST /{pk}/approve` (Darshaka → generates a
│                         new `sangha_sevi_id`; non-Darshaka → links to an existing
│                         `sangha_sevi_id` matching the claimed Local Sakha Number, or creates one
│                         with that number; either way creates `membership_sakha_affiliation` +
│                         activates the `user_account`), `POST /{pk}/reject` (leaves the account
│                         `PENDING_APPROVAL`, remarks required)
└── schemas/
    ├── auth.py           LoginRequest/Response, RefreshRequest/Response, ChangePasswordRequest,
    │                     ForgotPasswordRequest/Response, ResetPasswordRequest, MeResponse,
    │                     ScopeResponse, MessageResponse, UpdateProfileRequest
    └── admin.py          CreateUserRequest, ResetPasswordRequest, UpdateStatusRequest,
                          AssignRoleRequest, UserAccountResponse, UserDetailResponse,
                          UserListResponse, RoleAssignmentResponse,
                          CreateSanghaSeviRequest/Response
```

**New DDL (Tier 5):** `database/ddl/06_authentication/` (`user_account`,
`password_history`, `registration_claim`, `password_reset_token`, `user_session` — 5 tables) and
`database/ddl/07_administration/` (`user_role`, `admin_scope` — 2 tables), plus two tables added
to already-implemented modules: `database/ddl/04_family/06_family_admin.sql` (`family_admin` —
Family Admin role assignments, SOL-FAM-003 FAM-045..052) and
`database/ddl/05_membership/13_darshak_attendance_registration.sql`
(`darshak_attendance_registration` — cross-Sakha Darshak attendance with a 3-step approval
chain: Home Sakha → Parichalak → Target Sakha), plus one table added to Foundation:
`database/ddl/01_foundation/14_system_event_log.sql` (`system_event_log`) with a companion
`15_audit_trigger.sql` installing a DB-level `fn_audit_trigger()` on every `nss.*` table via a
`DO $$` loop. That's **9 new tables**, bringing the implemented total to **44**
(`database/README.md` has been updated for this branch and now reflects this count). Note:
`system_event_log` is populated by *both* the DB-level trigger and the app-level
`api/helpers.py::log_audit()` (called explicitly from `family.py`'s write endpoints) — the two
double-write for the same event with no de-duplication, accepted because `log_audit()` also
carries semantic actions (LOGIN/APPROVE) the trigger cannot express (see Gotchas). The table
count has since grown to **47** (see `database/README.md`).

**Removed (Tier 5):** every Tier 4 "verification" seed file
(`database/seed/02_organization/04_tier4_verification_orgs.sql`,
`database/seed/03_person/02_tier4_verification_persons.sql`,
`database/seed/04_family/01_tier4_verification_family.sql` +
`02_tier4_verification_family_links.sql`,
`database/seed/05_membership/01_tier4_verification_membership.sql`,
`database/seed/99_extended_test_data.sql`, `database/seed/99_fix_memberships.sql`) and
`database/migrations/` in its entirety (`README.md`, `add_performance_indexes.sql` — now folded
directly into the respective table DDL — and `update_darshaka.sql`, superseded by a corrected
seed value). **The database now ships with zero demo Person/Family/Membership data** — real data
is meant to be created through the registration/approval flow (see Key Workflow #9) or the new
`database/seed/04_admin/01_admin_bootstrap.sql` (a single admin superuser, `P1`/`SS1`, seeded via
`scripts/bootstrap_admin.py` because its `user_account.password_hash` needs a runtime Argon2
hash — not run by plain `psql`). `database/fixes/` — a new, narrow one-off data-repair-script
folder (successor convention to the removed `migrations/`, never wired into any build script) —
has since been deleted outright: its only file, `fix_missing_ghost_transitions.sql`, hardcoded
UUIDs from the now-deleted demo seed data and was verified obsolete (the case it patched is
already handled by `family.py`'s auto-transfer logic). There is no `database/fixes/` folder on
disk anymore.

**Test infrastructure changed (Tier 5):** `tests/conftest.py` no longer opens a fresh
`TestClient`-only connection per module — it now holds one **session-scoped write-pool
connection** for the whole pytest run, opens a `SAVEPOINT` per test module, and both
`get_connection`/`get_write_connection` FastAPI dependencies are overridden to yield that same
connection. Every module's `ROLLBACK TO SAVEPOINT` at teardown undoes all INSERTs/UPDATEs/
sequence increments the module's tests (and the API endpoints they call) made — this is what
makes the zero-seed-data change above tolerable: `test_admin.py`/`test_auth.py`/
`test_registration.py`/etc. create their own throwaway users/persons via `write_conn` and rely on
rollback for cleanup, rather than depending on any pre-seeded Tier 4 data. Per-file test counts and suite totals: `tests/README.md`.

### Tier 6 (Governance) — in progress, uncommitted on `feature/tier6-governance`

Not yet released; verified from the working tree (`git status`), not from a release note. Counts below were taken from code: 15 routers / 201 endpoints in `api/main.py` (137 at v0.11.0).

**Database (`database/ddl/08_governance/`, 10 tables + 1 trigger function).** `body_type_master`, `position_master`, `body_master` (nullable `organization_pk`: NSS-wide bodies have NULL), `body_member_assignment` (partial unique index on active holder; deliberately no DB seat-count limit), `acting_position_assignment`, `election` (`election_type` ELECTION|NOMINATION; a NOMINATION cycle cannot have voting dates or reach VOTING), `election_nomination`, `election_vote`, `election_result`, `election_vote_participation` (records *who* voted, not *what*, enabling secret ballots). `11_governance_immutability.sql` defines `nss.fn_block_update()` and BEFORE UPDATE triggers on `election_vote` and `election_vote_participation`; DELETE stays allowed for the ballot "reset" flow. Seeds (`database/seed/08_governance/`): 8 body types, 10 positions, 3 singleton bodies (KENDRA_GB, ADVISORY_BOARD, KENDRA_MAHILA_PM).

**Build scripts.** `02_build.sh/.ps1` and `render_build.sh` gain Phase 11b (governance DDL), 11c (governance seed) and 11d (correspondence DDL, 4 tables in `database/ddl/09_correspondence/`, incl. `correspondence_sequence_counter`; API in `correspondence.py`, schema-only tests in `tests/db/test_correspondence_schema.py`; `03_validate.*` checks existence of 3 of them); Phase 7 grows to 16 tables (`17_sakha_local_number_counter.sql`, `18_membership_change_request.sql`). `03_validate.*` adds a Governance module block. Optional Phase 15 (`RUN_DEMO_SEED`, gitignored `seed/demo/nss_demo_seed.sql`) exists only in `02_build.sh`. Because the build is existence-gated per table, a redeploy over an existing DB will **not** pick up: the `NSS_ERP_ADVISORY_BOARD_ADMIN` role row, the 3 added body types, the widened `admin_scope`/`role_master` CHECKs, or `election.election_type` (all election endpoints then fail with `column "election_type" does not exist`) — a full rebuild is required.

**RBAC.** New permissions `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE` (23 total; 25 with `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE`, 140 role mappings) granted to NSS/Kendra/Sakha admins (both) and Anchalika/Zilla/Patha Chakra/Kendra Mahila admins + Auditor (view). New role `NSS_ERP_ADVISORY_BOARD_ADMIN` (scope level `ADVISORY_BOARD`, 10 roles total) is not assigned through `user_role`: `rbac_service.load_composite_grants()` auto-grants it (§63) to holders of PRESIDENT/SECRETARY in the Advisory Board body; `GET /admin/users/{pk}` exposes this as `auto_granted_scopes`.

**API.** `api/routers/governance.py` (46 endpoints, `/api/v1/governance`): catalogue CRUD, bodies, assignments (end / `resign` self-service / request-/approve-/reject-removal), `/advisory-board/missing-nominations`, `/me/parichalak-status`, `/bodies/sakha-scope-options`, acting assignments, elections with status transitions, nominations, votes (officer-recorded and `/votes/self`), tally, results and `apply`. Reads use the read pool; writes use `api.dependencies.auth.get_write_connection`. Org scoping goes through `actor_scope_org_pks`/`require_org_in_scope`. `membership_change_request.py` (5 endpoints) implements the Sakha Transfer / Apply-for-Darshak release→accept workflow. `correspondence.py` (9 endpoints, `/api/v1/correspondence`, `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE` + admin scope on `register_organization_pk`) covers register/list/detail, status transitions (§6.2; reopen needs remarks), responsible-party assignment and document / finance-reference sub-resources; reference numbers come from `helpers.next_correspondence_reference_number()` backed by `correspondence_sequence_counter` and need the register org's `short_code` (else 422). `admin.py` gains 4 `/credentials/members*` endpoints. `membership.py::search_members` takes an optional subtree-aware `organization_pk`. New helpers in `api/helpers.py`: `next_sakha_local_number`, `close_sakha_affiliation`, `log_patra_history`, `set_membership_credential_status`. For Darshaka (PROBATIONARY) the Local Sakha Number is optional in `registration.py` (`register`, `claim_existing`, via `is_probationary_membership_type`) and is system-generated at admin approval; the register page hides the field only in its standalone "Apply for Darshak" flow (`darshakFlow`).

**Frontend.** `admin.html`/`admin.js`: Governance nav group (Catalog, Bodies, Assignments, Elections tabs; gated on `canViewGovernance`/`canManageGovernance`). `dashboard.html`/`dashboard.js`: "Open Elections — Cast Your Vote", Governance Bodies view, and "My Change Requests".

**Tests.** `tests/api/test_governance.py` (65), `tests/api/test_admin_credentials.py` (16), `tests/api/test_membership_change_request.py` (28), `tests/api/test_correspondence.py` (26), `tests/db/test_correspondence_schema.py` (14) and security suites for governance (13), membership change requests (11) and correspondence (24). `tests/conftest.py` now imports `get_write_connection` from `api.dependencies.auth`.

### `frontend/` — Login + Registration + Member Dashboard + Administration Dashboard detail

**Current contents (verified on disk):** `login.html`, `register.html`, `dashboard.html`,
`admin.html`, `README.md`, and `assets/` (`css/`: `style.css`, `badges.css`, `nss-layout.css`,
`nss-datepicker.css`, `nss-combobox.css`, `tailwind-input.css`, `tailwind.min.css`; `img/`: `nss-logo.png`,
`nss-logo-original.png`, `ssm-mandir.webp`; `js/`: `login.js`, `register.js`, `dashboard.js`,
`admin.js`, `auth.js`, `nss-config.js`, `nss-layout.js`, `nss-datepicker.js`, `nss-dialog.js`,
`nss-location.js`, `nss-combobox.js` (select-or-propose dropdown for geography; loaded by register/dashboard/admin but not yet instantiated by any page), `org-dashboard.js` (new in Tier 5 — shared "Org Dashboard" tab component,
see below)). See "Tier 5 frontend" below the tree for the per-page detail.

> **⚠ Historical.** The tree immediately below documents the six Tier 0-4 standalone
> verification pages (`index.html`, `foundation.html`, `organization.html`, `person.html`,
> `family.html`, `membership.html`) and their per-page JS (`app.js`, `foundation.js`,
> `organization.js`, `person.js`, `family.js`, `membership.js`). **All twelve files have been
> deleted from disk.** Their functionality was folded into `admin.html` (Bootstrap RBAC →
> System Settings; Foundation → Reference Data + Geography; Organization → Organizations +
> Organization Hierarchy; Person → Person Directory; Membership → Member Directory) and
> `dashboard.html` (Family → Family tab; Membership → Membership tab). The tree is kept as a
> record of where each piece of `admin.html`/`dashboard.html` logic originally came from; the
> shared `assets/css/badges.css` and `assets/js/nss-config.js` entries in it are still current.

```
frontend/
├── index.html          Tier 0 Bootstrap Verification UI entry point — a centred System Status
│                        card above a responsive grid (1 column mobile, 2 tablet/`md`, 3
│                        desktop/`xl`) of RBAC Roles / Permissions / Role Permissions cards;
│                        Alpine.js directives bound to `bootstrapApp()` (declared via `x-data`);
│                        nav bar links to `/foundation`, `/organization`, `/person`, `/family`,
│                        and `/membership`
├── foundation.html      Tier 1 Foundation Verification UI entry point — same System Status card,
│                        then a 4-tab layout (`foundationApp()`, tabs `tabs-boxed`): Master Data
│                        (categories + filterable master-data table), System Config (settings +
│                        ID sequences, `current_value` deliberately not shown), Geographic
│                        (country→state→district→city/village drill-down + postal codes),
│                        Runtime Tables (document_master; notes `field_change_log` exists in the
│                        DB but isn't exposed until Tier 5/auth); nav bar links to `/`,
│                        `/organization`, `/person`, `/family`, and `/membership`
├── organization.html    Tier 2 Organization Verification UI entry point — same System Status
│                        card, then a 3-tab layout (`organizationApp()`, tabs `tabs-boxed`):
│                        Reference Data (org types + statuses), Organizations (list filterable by
│                        `type_code`/`status_code`, click-to-drill-down into a selected org's
│                        `/children`), Hierarchy (the flat recursive-CTE result rendered as an
│                        indented tree via `depthIndent(depth)`); note the newer
│                        `/children-stats` endpoint's own docstring claims org-admin-sidebar UI
│                        wiring for inline drill-down counts, but no such wiring actually exists
│                        in this file or `organization.js` yet — a real implementation gap; nav bar
│                        links to `/`,
│                        `/foundation`, `/person`, `/family`, and `/membership`
├── person.html          Tier 3 Person Verification UI entry point — same System Status card,
│                        then a 2-tab layout (`personApp()`, tabs `tabs-boxed`): Persons (list
│                        filterable by `gender_code`/`marital_status_code`/`blood_group_code`,
│                        click-to-drill-down into a selected person's full detail + resolved
│                        addresses), Search (debounced `pg_trgm` fuzzy search against `/search`);
│                        masked Aadhaar (`aadhaar_last4` only) shown in the detail panel; nav bar
│                        links to `/`, `/foundation`, `/organization`, `/family`, and
│                        `/membership`
├── family.html          Tier 4 Family Verification UI entry point — same System Status card,
│                        now a 3-panel layout (`familyApp()`): sidebar (family list, filterable),
│                        a recursive family-tree renderer (`buildTree()`/`renderTree()`/
│                        `_renderSubtree()`/`_renderCouple()`/`_renderPerson()`) consuming
│                        `/families/{pk}/graph?viewer_person_pk=` — labels are computed
│                        server-side by `api/services/family_graph.py`, not stored; a "View as"
│                        viewer selector (`changeViewer()`) re-fetches `/graph` from a different
│                        person's perspective; Sakha-alignment mismatch badges consuming
│                        `/sakha-alignment` (`fetchSakhaAlignment()`, `isMemberSakhaMismatch()`);
│                        and a Selected Person detail panel that also calls
│                        `/person/{pk}/membership-summary` to bridge into membership context
│                        (`selectPerson()`); nav bar
│                        links to all other five pages
├── membership.html      Tier 4 Membership Verification UI entry point — the largest frontend
│                        page (~840 lines); `membershipApp()` drives a member list + detail panel
│                        (Sakha affiliation history, Parichaya Patra, Anumati Patra, journey
│                        timeline) plus a search tab implementing the 7-field member search and
│                        4-field person search (inline detail panel on selection, single-result
│                        auto-select, matching Person's inline-panel pattern); nav bar links to
│                        all other five pages
├── assets/
│   ├── css/style.css   One rule: hides `[x-cloak]` elements until Alpine.js initializes
│   ├── css/badges.css  **New (Tier 4)** — single source of truth for every
│   │                   `badge-status-*`/`badge-type-*`/`badge-aff-*`/`badge-gender-*`/
│   │                   `badge-marital`/`badge-role-*` CSS class, plus `.data-sevi-id`/
│   │                   `.data-erp-no`/`.data-kendra-no`/`.data-family-id`/`.data-label`
│   │                   typographic classes for the three-tier identity display. All 6 pages
│   │                   now `<link>` this in `<head>` and their old duplicate inline
│   │                   `badge-status-*` `<style>` blocks were removed — verified zero leftover
│   │                   duplication across all 6 HTML files. Convention: pages must NOT redefine
│   │                   these classes locally.
│   ├── img/nss-logo.png NSS logo, copied from `NSS LOGO/logooo.png`
│   ├── js/nss-config.js **New (Tier 4)** — global `NSS` object, shared by all 6 pages:
│   │                   `TYPE_DISPLAY_NAMES` (Bye-Law display overrides — `PROBATIONARY` →
│   │                   "Darshaka" — overriding `master_data.value_name` for portal display),
│   │                   badge-class lookup maps (`STATUS_BADGE_MAP`, `TYPE_BADGE_MAP`,
│   │                   `AFF_BADGE_MAP`, `GENDER_BADGE_MAP`) with helper methods
│   │                   (`typeDisplayName()`, `statusBadgeClass()`, etc.), and document-visibility
│   │                   rules (`showParichayaPatra()` always `true`; `showAnumatiPatra()` false
│   │                   for `ASSOCIATE` type, per MBR-019A/B)
│   ├── js/app.js        Defines `bootstrapApp()` — Alpine data component with health/roles/
│   │                    permissions/selectedRole state and fetch methods against
│   │                    `/api/v1/bootstrap/*` (relative paths, `API_BASE = "/api/v1/bootstrap"`)
│   ├── js/foundation.js Defines `foundationApp()` — Alpine data component, `FND_API =
│   │                    "/api/v1/foundation"`; lazily loads each tab's data on first visit
│   │                    (`loadMasterTab()`/`loadConfigTab()`/`loadGeoTab()`/`loadRuntimeTab()`),
│   │                    toggle-deselect on country/state/district selection
│   ├── js/organization.js Defines `organizationApp()` — Alpine data component, `ORG_API =
│   │                       "/api/v1/organization"`; lazily loads each tab's data on first visit
│   │                       (`loadReferenceTab()`/`loadOrganizationsTab()`/`loadHierarchyTab()`);
│   │                       `selectOrganization()` toggles a row and fetches its `/children`;
│   │                       `filterOrganizations()` re-fetches on `type_code`/`status_code` change;
│   │                       has no reference to `/children-stats` (see `organization.html` note above)
│   ├── js/person.js     Defines `personApp()` — Alpine data component, `PERSON_API =
│   │                    "/api/v1/person"`; `fetchFilterOptions()` uses `Promise.allSettled` (the
│   │                    only such usage in the codebase) since gender/marital-status/blood-group
│   │                    options come from three independent Foundation `master_data` queries;
│   │                    `selectPerson()` fetches detail + addresses in parallel with asymmetric
│   │                    failure handling; `selectPersonByPk()` bridges search results into the
│   │                    detail panel; `executeSearch()` is debounced (the only debounced fetch in
│   │                    the codebase) against `/search?q=`
│   ├── js/family.js     Defines `familyApp()` — Alpine data component, `FAMILY_API =
│   │                    "/api/v1/family"`; grew substantially in Tier 4 (from a simple
│   │                    list/filter/detail component to ~850 lines) to add the recursive
│   │                    tree-rendering functions, the viewer-selector, and Sakha-alignment
│   │                    fetch/mismatch-detection logic described in `family.html` above
│   └── js/membership.js Defines `membershipApp()` — Alpine data component, `MEMBERSHIP_API =
│                        "/api/v1/membership"`; the 7-field member search and 4-field person
│                        search share the same debounced-fetch/inline-detail-panel pattern
│                        `personApp()` established; delegates badge-class/display-name lookups
│                        to the new shared `NSS.*` helpers instead of local logic
└── README.md            Full file/function/state-property reference for all six pages — see it
                          directly for detail rather than duplicating it here
```

None of the six retired pages was an admin dashboard — all were Tier-scoped verification UIs
proving the database→API→frontend chain end to end for their tier, and none had any login,
session or credentials by design. They have been superseded by the four authenticated Tier 5
pages described next, which are not an extension of the six but a replacement for them. Tech
stack is unchanged and still current: Tailwind CSS + DaisyUI
(pre-built via Tailwind CLI — root `package.json`/`tailwind.config.js`, output
`frontend/assets/css/tailwind.min.css`, ~87 KB, committed; previously CDN-loaded, migrated on
`develop` — see Architecture above) + Alpine.js (CDN,
pinned to `3.14.8` with SRI `integrity`/`crossorigin`, unchanged by the migration) — no
frontend framework, no
Django templates. Served entirely by FastAPI (see `api/` detail above); no separate frontend
server is needed since every page is same-origin with the API. Every fetch method across
`app.js`, `foundation.js`, `organization.js`, `person.js`, `family.js`, and `membership.js`
followed the same
pattern: set loading/error state → try/fetch/parse → catch sets an error flag (never exposes
raw error text to the UI) → finally clears loading — a pattern `dashboard.js`/`admin.js`
inherited.

**Tier 5 frontend — the current frontend:** four pages exist — `login.html`, `register.html`,
`dashboard.html`, `admin.html` — plus their backing JS (`login.js`, `register.js`,
`dashboard.js`, `admin.js`) and shared helpers `auth.js` (`NSSAuth` — JWT storage/refresh +
authenticated `fetch()` wrapper), `nss-layout.js` (`NSSLayout` — sidebar/topbar mixin shared by
`admin.html`/`dashboard.html`), `nss-datepicker.js`/`nss-dialog.js`/`nss-location.js`, and
`org-dashboard.js` (new in Tier 5 — see below), backed
by two new shared stylesheets `nss-layout.css`/`nss-datepicker.css` (not yet in
`frontend/README.md`'s file reference). There is no standalone
`forgot-password.html` and no `/forgot-password` page route by design — the
forgot/reset-password flow is implemented inline on the Login page
(`login.html` / `loginApp()`, toggled via `showForgotPassword` /
`showResetPassword`).
**`claim-approval.html` was never built as a standalone page, and this is not a gap** — the
Sakha-admin review queue for `registration_claim` rows (`api/routers/claim_approval.py`) shipped
as a "Registration Approvals" tab inside `admin.html`/`admin.js` instead (list w/ status filter
+ pagination, detail view, inline edit, pending-count sidebar badge, `canApproveClaims`
permission gate, and a "View Claim" jump-link from the Person Directory tab). See
`frontend/README.md` for the full per-page/per-file reference
(not duplicated here, matching this document's existing convention for the Tier 0-4 pages'
`README.md` pointer above).

**`admin.html`/`admin.js` changes (this branch's latest work):** a new **"Assign
Sakhas" tab** (`activeTab === 'assignSakha'`) lets an admin search/filter Sakha Sanghas and
re-parent one to its real Anchalika/Zilla Sangha via the new `PATCH /api/v1/admin/
organizations/{pk}` `parent_organization_pk` field (see Tier 5 `admin.py` above). The
**"Create Person" tab was restructured into a real 3-step flow**: Step 1 Person (find-or-create)
→ Step 2 Sangha Sevi (`createSanghaSeviForNewPerson()` against `POST /api/v1/admin/sangha-sevi`,
its own step now, with a `skipCreateSanghaSevi()` "Skip for now" option) → Step 3 Account
Credentials (no longer bundles Sangha Sevi creation into the account-creation submit). A
`sakhaShortCode(orgPk)`/`sakhaMissingShortCode(orgPk)` helper pair now backs both this flow's
Step 2 and the standalone Create Sangha Sevi tab, replacing a duplicated inline lookup
expression. `canEditOrg(org)` is now subtree-aware (walks the org's parent chain via a new
`isOrgOrDescendantOf()` helper) rather than matching only the admin's exact own org row — a
Zilla/Anchalika admin now sees Edit/Short-Code buttons on descendant Sakhas too, matching the
backend's subtree-aware scope check (see Tier 5 `admin.py` above). A `tabLoaders` map in
`init()` fixes a hash-based tab-restoration bug: refreshing the page while on a lazy-loaded tab
(Organization Hierarchy, Assign Sakhas, Person Directory, etc.) used to leave it permanently
empty since only the `claims` tab had its data-loader wired to fire on hash-restore;
`activeTab` itself is now also resolved synchronously from `window.location.hash` before
Alpine's first render (previously flashed the default "users" tab first).

**`api/main.py` gained automatic per-request asset cache-busting (Tier 5).**
`_render_html_with_asset_versions()`/`_serve_page()` rewrite every `/assets/js/*.js` and
`/assets/css/*.css` reference in each served HTML page to `?v=<10-char sha256 prefix of that
file's current contents>`, computed per request but memoized by file mtime (an unchanged file
is never re-hashed). This replaces the old hand-maintained `?v=N` convention (all manual `?v=`
strings were stripped from `login.html`/`register.html`/`dashboard.html`/`admin.html`) — the
old approach had already drifted (the same shared file carried different `?v=` numbers on
different pages) and relied on a human remembering to bump it on every edit. Every page route
now serves through `_serve_page()` instead of a bare `FileResponse`; the HTML response itself
still carries `Cache-Control: no-store`, so only `/assets/*` (86400s cache, `middleware.py`)
relies on the content hash to invalidate correctly. `NSSLocation.create()`
(`frontend/assets/js/nss-location.js`) gained a `basePath` option (default
`/api/v1/foundation`) so `register.js` can point the same shared location-cascade helper at the
new public `/api/v1/register/*` endpoints instead (see `registration.py` above) — `admin.js`'s
own usage is unaffected (still defaults to `/api/v1/foundation`).

**`dashboard.js`'s family-tree logic was consolidated (Tier 5).** The Family tab and the
Family-of-Origin org browser inside `dashboard.html` each used to independently implement the
entire couple-tree-building and tree-rendering algorithm (~90+ duplicated lines); both now share
`_buildCoupleTree(allPersons)` and `_renderGenSubtree(nodes, isRoot, renderCouple, recurse)`.

**New shared `org-dashboard.js` component (v0.11.0).** One Alpine component,
`orgDashboardTab()`, embedded as an "Org Dashboard" tab inside both `admin.html` and
`dashboard.html`'s existing sidebar/topbar shell (not a standalone page — both hosts instantiate
it in a nested `x-data` scope via `openOrgDashboard(orgPk)`). Renders one of six layouts
depending on the viewed org's type — Sakha, Anchalika, Zilla, Kendra (each matching one of the
`docs/03_Solution/ui/mockups/0{2,3,5,6}_*_dashboard.html` mockups), plus Patha Chakra and Mahila
Sangha (no mockup of their own — reuse the same card idiom rather than a new visual language) —
one dashboard per organizational role in `role_master` (SOL-ADMIN-004 §8.7). Consumes the new
`GET /api/v1/organization/organizations/{pk}/stats` and
`GET /api/v1/membership/organizations/{pk}/darshak-summary` endpoints (see the `organization.py`/
`membership.py` detail above). Every number shown is real; the two mockup widgets that would
have needed attendance-%/renewal-tracking data (which no DB table backs) are rendered as honest
"not tracked yet" placeholders instead of fabricated figures, and the two Zilla "insights"
widgets that depended on that missing data were swapped for ones backed by real data
(largest/smallest Sakha by member count). This replaces an earlier standalone `/org-view` page
and route, which have been deleted entirely rather than merely retired — no doc should still
reference `org-view.html`/`org-view.js`/`/org-view`.

### `docs/01_Authoritative_References/NSS/` detail

Source-faithful transcription of the official NSS Bye-Law (`BY-LAW/NSS/NSS BYE-LAW.pdf`,
cross-checked against `BY-LAW/NSS/NSS_Bye_Law.docx`), organized by legal section:

```
NSS/
├── SECTION-A_PRELIMINARY_AND_GENERAL_PROVISIONS/   REF-001 — Name, Registered Office, Preamble, Objects, Memorandum of Association
├── SECTION-B_MEMBERSHIPS/                          REF-002 — Probationary/Regular/Associate Members, Cessation
├── SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA/    REF-003-C…009 — Governing Body, its Functions, and all 6 office-bearer duties;
│                                                    plus the two 1975 amendment Resolutions (REF-003-C(i)(2)-1975-01,
│                                                    REF-003-C(i)(8)-1975-02), filed adjacent to the clauses they amend
├── SECTION-D_ADVISORY_BOARD/                       REF-003-D
├── SECTION-E_GENERAL_BODY/                         REF-003-E
├── SECTION-F_FUNDS_OF_THE_KENDRA_SANGHA/           REF-003-F[A] (Funds), REF-003-F[b] (Maintenance), REF-003-F[c] (Utilisation) — 3 documents
├── SECTION-G_ACCOUNTS_AND_AUDIT/                   REF-003-G
├── SECTION-H_POWER_TO_AMEND/                       REF-003-H
└── SECTION-I_DISSOLUTION/                          REF-003-I
```

**No "Section J" exists in the source Bye-Law.** The Bye-Law's statutory sections end at
Section I (Dissolution); the two 1975 Resolutions that follow in the source text are explicit
amendments to Section C (inserting sub-clauses into Functions of the Governing Body and Duties
of the Secretary/Parichalak), not a standalone section. The content is filed as the two Section
C amendment documents above, not under an invented Section J.

Each REF document's clause-level numbering (numerals, letters, roman numerals) matches the
source exactly. `REF-001` additionally preserves the Memorandum of Association's
founding-members table (9 names + addresses), witnesses table, and the source's three distinct
certification/signature blocks (Memorandum, post-Dissolution, and post-Resolution) as separate,
non-deduplicated content, since all three appear separately in the source.

### `docs/01_Authoritative_References/MAHILA_SANGHA/` detail

Source-faithful transcription of the Nilachala Saraswata Mahila Sangha's own Constitution &
Bye-Law (`BY-LAW/NSS - Mahila Sangha/NSS Mahila Sangha By-Law.pdf`, cross-checked against
`BY-LAW/NSS - Mahila Sangha/NSS_Mahila_Sangha_Bye_Law.docx`) — a sibling folder to `NSS/`, not
nested under it, since Mahila Sangha is a separately registered entity with its own Bye-Law.
Uses a dedicated `REF-MS-XXX` identifier family (distinct from NSS's `REF-00X` family):

```
MAHILA_SANGHA/
├── SECTION-A_MEMORANDUM_AND_REGISTRATION/  REF-MS-MOA — Certificate of Registration, Memorandum, founding Governing Body + signatories + witnesses, historical 1989-1991 roster
├── SECTION-B_AIMS_AND_OBJECTS/             REF-MS-1
├── SECTION-C_MEMBERSHIP/                   REF-MS-2
├── SECTION-D_ENROLMENT_PROCEDURE/          REF-MS-3
├── SECTION-E_CESSATION_OF_MEMBERSHIP/      REF-MS-4
├── SECTION-F_CONSTITUTION_OF_THE_SANGHA/   REF-MS-5
├── SECTION-G_GOVERNING_BODY/               REF-MS-6(i)…6(viii) — Constitution, Powers & Duties, and all 6 office-bearer duties
├── SECTION-H_FUNDS/                        REF-MS-7(i)/(ii)/(iii) — Comprising/Maintenance/Utilisation, 3 documents mirroring NSS's own Funds-section split
├── SECTION-I_LEGAL_REPRESENTATION/         REF-MS-8
├── SECTION-J_AUDIT/                        REF-MS-9
├── SECTION-K_DISPUTE_SETTLEMENT/           REF-MS-10
├── SECTION-L_POWER_TO_AMEND/               REF-MS-11
└── SECTION-M_DISSOLUTION/                  REF-MS-12
```

22 documents total, all verified against source with clause numbering (numerals/letters/roman
numerals) preserved exactly as printed, including source quirks (no labeled "b)" sub-item in
Clause 6(ii); Clause 8 has no heading title at all — title assigned editorially). Every
REF-MS document's "Related Governance" section cites `AUTH-001` as the source defining the
`REF-MS` identifier family — `AUTH-001` defines it via `AUTH-ID-002A` and the Appendix B family
mapping, backed by `GDR-002`.

### `database/` detail

The block below was rewritten in this documentation pass against the current `database/` tree;
for full per-file detail see `database/README.md` and the per-folder READMEs.

```
database/
├── scripts/              00_create_database.sql (superuser, postgres DB: creates nss_erp
│                         database + nss_db_owner/nss_db_backend/nss_db_writer roles, all LOGIN,
│                         no password, via dblink),
│                         01_extensions.sql (superuser, nss_erp: pgcrypto/pg_trgm/btree_gin/postgis,
│                         nss schema),
│                         02_build.sh/.ps1 (runs all implemented DDL+seed in Phases 0-14; both
│                         are v2.6; only the .sh has the existence-gated run_ddl/run_seed model),
│                         03_validate.sh/.ps1 (row-count/FK integrity checks; no Family/Membership
│                         coverage),
│                         04_grant_backend.sql (nss_db_backend read-only SELECT on nss.*),
│                         05_create_writer_role.sql (nss_db_writer SELECT + INSERT/UPDATE, no DELETE),
│                         06_setup_env.sh (role passwords + api/.env; bash only) — see
│                         scripts/README.md for the full database-to-running-API sequence and
│                         phase-by-phase execution table
├── ddl/                  48 tables in total (see database/README.md)
│   ├── 00_bootstrap/     3 tables: role_master, permission_master, role_permission (RBAC
│   │                     definitions, created before Foundation — zero FK dependencies;
│   │                     SOL-ARCH-011). Owned by Administration; see Gotchas for the
│   │                     role-catalogue discrepancy
│   ├── 01_foundation/    15 tables: master_category, system_setting, id_sequence_master, country,
│   │                     document_master, field_change_log, master_data, state, district,
│   │                     city_village, postal_code, post_office (files 02-13),
│   │                     system_event_log (14), festival_master / festival_calendar_date (16-17),
│   │                     plus 15_audit_trigger.sql (fn_audit_trigger(), attached to every other
│   │                     nss.* table; runs last, Phase 14). district/postal_code/post_office/
│   │                     city_village carry member-assisted-entry columns (entry_status etc.)
│   ├── 02_organization/  1 table: organization (self-referencing hierarchy, address inline, no
│   │                     `organization_address` table) + 2 triggers (address restriction
│   │                     ORG-BR-099, Kumari/Sevak one-per-Sakha ORG-BR-102). The former
│   │                     `organization_type_master`/`organization_status_master` tables were
│   │                     retired — type and status are rows in Foundation's generic `master_data`
│   │                     (categories `ORGANIZATION_TYPE`, `STATUS`), referenced via
│   │                     `organization_type_master_data_pk`/`status_master_data_pk`. This
│   │                     diverges from the frozen generic 3-table structure; `organization_code`
│   │                     naming/width/nullability and the seeded type codes also don't yet match
│   │                     two separate frozen/design specs — see Gotchas
│   ├── 03_person/        2 tables: person, person_address (the superseded per-domain-master
│   │                     prototype file was deleted)
│   ├── 04_family/        6 tables (family_group, family_relationship, family_head_history,
│   │                     family_transition_history, family_link, family_admin) + move-transition
│   │                     guard trigger
│   ├── 05_membership/    14 tables (sangha_sevi first) + Sakha-only trigger (MBR-038A) +
│   │                     16_foundation_audit_fk.sql (ALTER-only, Phase 7b)
│   ├── 06_authentication/ 5 tables (Tier 5): user_account, password_history, registration_claim,
│   │                     password_reset_token, user_session
│   └── 07_administration/ 2 tables (Tier 5): user_role, admin_scope
└── seed/
    ├── 00_bootstrap/     `role_master`: 10 roles seeded (3 SYSTEM + 7 ORGANIZATIONAL,
    │                     matching SOL-ADMIN-004 §8.7 frozen catalogue);
    │                     `permission_master`: 21 permissions; `role_permission`: 113 mappings
    ├── 01_foundation/    13 seed files (01-11b): 13 master categories, 89 master data values
    │                     (GENDER/MARITAL_STATUS/ADDRESS_TYPE/DOCUMENT_TYPE/MEMBERSHIP_TYPE/
    │                     STATUS/RELATIONSHIP_TYPE/ORGANIZATION_TYPE/BLOOD_GROUP; `STATUS` is a
    │                     unified cross-module category, 16 values; `ORGANIZATION_TYPE` 13 values),
    │                     14 ID sequences (PERSON zero-padded to 10 digits — see Gotchas; SAKHA
    │                     unpadded), 5 countries, 112 states, ~770 districts (India only), 5 system
    │                     settings, all-India postal codes (`08b`, ~17.9k PINs), post offices
    │                     (`08c`), Dola Purnima festival calendar 2024-2028 (`10`), ~673k
    │                     city_village rows (`11`/`11b`); `09_sakha_postal_codes.sql` runs in Phase 4
    ├── 02_organization/  3 unique named organizations (Kendra, Nilachala Kutira, Smruti
    │                     Mandira) + 175 real Sakha branches (`05_sakha_branches.sql`) + org-code
    │                     counter sync; organization type and status seed data live in
    │                     `01_foundation/` `master_data`, not here
    ├── 03_person/, 04_family/, 05_membership/   README only — no seed data
    └── 04_admin/         the single admin superuser (P1/SS1), run via scripts/bootstrap_admin.py
```

### `docs/03_Solution/` detail

```
03_Solution/
├── modules/
│   ├── organization/     01_module_overview/02_erd/03_lifecycle/04_business_rules/05_table_design (v1.1.0, GOVERNANCE ALIGNED); walks back the ANCHALIKA/ZILLA/SAKHA/PATHA_CHAKRA type-to-type parent matrix to an OPEN item — only the generic apex + self-referencing 3-table structure is frozen. Implemented in SQL, matching that generic structure — but the implemented `organization_code` column (VARCHAR(10), nullable) doesn't match `ORG-PENDING-001`'s frozen `organization_short_code` spec (VARCHAR(5), NOT NULL), and seeded type codes (`ANCHALIKA_SANGHA` etc.) don't match this doc's short forms (`ANCHALIKA` etc.) — see Gotchas
│   ├── person/            same pattern + README.md, v1.0.0 SOURCE ALIGNED, 5 files — **1 table** (`person` only — `document_master` is Foundation-owned); docs name the business identifier `person_id`, conflicting with the implemented DDL's `person_code` (see Gotchas); address/Aadhaar/photo/blood-group explicitly left OPEN despite `person_address` already existing in SQL
│   ├── membership/         01-05 overview/erd/lifecycle/business_rules/table_design, all DRAFT — no corresponding API/backend code exists yet (see Gotchas)
│   ├── family/             5 files, frozen 4-table design — no corresponding API/backend code exists yet (see Gotchas)
│   ├── attendance/         6 files (business_rules/table_design/review_workflow at slots 04/05/06, FROZEN) + DARSHAK_BUSINESS_RULE.md (see below) — zero corresponding backend code
│   ├── heritage/           01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED — 8 tables designed (founder_master + teachings/objectives/milestones/publications/office-bearers + 2 lookup masters); zero implementation exists (no API/backend code) for any of the 8 designed tables
│   ├── kumari/             01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED (document-Status DRAFT) — KM000001 ID format
│   ├── kishor/            01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED (document-Status DRAFT) — KH000001 ID format + frozen v2.1 Guardian Model (Guardian must independently qualify via `sangha_sevi` identity)
│   ├── mahila/             01-05 overview/erd/lifecycle/business_rules/table_design, v2.1.0 — one body, two names (Mahila Governing Body = Mahila Parichalana Mandali); freezes the Mandali term at 2 years (MAH-040)
│   ├── sevak/              01-06 core sequence (only 06_table_design FROZEN, rest DRAFT/consolidation-in-progress) + sangha/, seva/, events/ subdocs; core SEV-001..040
│   ├── foundation/         01-04 overview/erd/business_rules/table_design, v1.0.0 SOURCE ALIGNED — describes 10 tables: the original 8 (master_category, master_data, system_setting, id_sequence_master, country, state, district, city_village) plus `document_master` and `field_change_log`, Foundation-owned shared infrastructure (`DOC-ARCH-001`, `CROSS_MODULE_PRINCIPLES.md`). **Implemented in SQL** — all 10 designed tables have DDL under `database/ddl/01_foundation/`, plus 2 more the design doc doesn't describe yet (`postal_code`, `city_village_postal_code_map`) — see Gotchas
│   ├── administration/     10 files (5 RBAC/Bootstrap docs + 1 Bootstrap RBAC column-level design + 4 Correspondence Register docs) — v1.0.0/v1.2.0 SOURCE ALIGNED — **8 Administration-owned tables**: the 5 RBAC tables (role_master, permission_master, role_permission, user_role, admin_scope — the first 3 also sequenced as "Phase 0 Bootstrap RBAC," `SOL-BOOT-001`/`SOL-ARCH-011`, DDL implemented and committed) plus 3 Correspondence Register tables (correspondence, correspondence_document, correspondence_finance_reference — `CORR-DECISION-003`); `user_account`/`password_history` are exclusively Authentication-owned per the Table Ownership Declaration. **Filename collision:** `06_bootstrap_rbac_table_design.md` and `06_correspondence_register_erd.md` share the same number — see Gotchas
│   ├── authentication/     Solution-layer "Authentication & Security", 5 files — v1.0.0 SOURCE ALIGNED — ERD still shows 7 tables, but exclusive ownership is only `user_account`+`password_history`; the other 5 RBAC tables are exclusively Administration-owned and appear here only for evaluation, not management. Argon2/JWT/session/Aadhaar-encryption/RLS as principles. No corresponding API/backend implementation exists yet for any of this module's tables
│   ├── governance/         Solution-layer ERP module, distinct from docs/00_Project_Governance/, 5 files — v1.0.0 SOURCE ALIGNED — Unified Body Governance Model (body_type_master, body_master, position_master, body_member_assignment, acting_position_assignment) + election entities (election, election_nomination, election_vote, election_result), 9 tables. **Freezes the Mahila Parichalana Mandali term at 3 years** (`04_governance_business_rules.md` GOV-BR-036) **and, per `03_governance_lifecycle.md`, a formal consensus→election→election-table reconstitution process** — both directly conflicting with mahila/'s own frozen **2-year** term (MAH-040) and its consensus-only reconstitution process; unreconciled, see Gotchas/Open questions. No corresponding API/backend implementation exists yet
│   ├── publications/       7 files (overview/erd/business_rules/table_design/functional_design/ui_workflow/notification_purchase_design), v1.0.0 SOURCE ALIGNED + USER REQUIREMENTS — zero new tables, reuses Heritage's nss_publication/publication_type_master/publication_language_master
│   ├── upbs/               01-04, v1.0.0 SOURCE ALIGNED — 7 tables (upbs_event, upbs_registration, delegate_card, prasad_patra, accommodation_allocation, camp_master, guest_reference); Day 1/2/3 ops + volunteer structure explicitly PENDING
│   ├── reports/            01-04, v1.0.0 SOURCE ALIGNED — 5 metadata/configuration-only tables (report_category_master, report_definition, report_filter_definition, dashboard, dashboard_widget); consumes but never duplicates other modules' data
│   ├── audit/              01-04, v1.0.0 SOURCE ALIGNED — 2 tables (audit_master, system_event_log)
│   ├── backup_technical/   01-04, v1.0.0 SOURCE ALIGNED — 2 tables (backup_master, restore_history)
│   ├── finance/            01-05 design/erd/business_rules/table_design/lifecycle, v1.0.0 SOURCE ALIGNED (ERD tagged DRAFT — LOGICAL DESIGN) — 7 tables (financial_year, financial_scope, fund_master, financial_transaction, financial_receipt, financial_payment, financial_transfer); derives from REF-003-F[A]/[b]/[c] and REF-MS-7(i)-(iii); Financial Scope Independence principle (FIN-ARCH-001) keeps Financial Scope distinct from Organization; correctly follows the project's `_code` business-identifier convention (contrast with the `_id`/`_code` conflict below); business rules FIN-BR-001–068
│   ├── programmes_events/  Module #21, 01-05 overview/erd/lifecycle/business_rules/table_design, v0.1.0 DRAFT — the one module NOT tagged SOURCE ALIGNED; "ARCHITECTURALLY JUSTIFIED" per its cross-module review but "FORMAL MODULE FREEZE PENDING." Programme Type → Event Instance two-level model (Organization ≠ Event Location; Patha Chakra = Organization Type, not Event/Programme Type). **7 candidate common tables**: `programme_type`, `event`, `event_day`, `event_session`, `event_registration`, `event_location`, `event_history` — all cross-module reconciliation gates closed (`SOL-EVT-007`) but still none frozen DDL. Backed by 7 cross-module architecture docs — see `architecture/` below.
│   └── assets_property/    Module #22, 01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 DRAFT — SOURCE ALIGNED. Manages the physical/administrative record of NSS movable/immovable property and assets: `Property`/`Asset` as primary entities plus `Custodianship`, `Statutory Record`, `Maintenance Record`. 7 tables: `property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`. 74 business rules (`AP-001`–`AP-074`: 24 CONSTITUTIONAL, 32 ERP, 13 CROSS-MODULE, 5 PENDING). Depends only on Foundation + Person + Organization (no hard FK to Finance); sits at Tier 6 per `IMPLEMENTATION_DEPENDENCY_ORDER.md`.
├── api/                   Consolidated read-only API contract docs, one per implemented tier —
│                          moved out of `architecture/` into this dedicated folder (was
│                          scattered there previously; see the Gotcha on this move below)
│   ├── README.md
│   ├── BOOTSTRAP_API_CONTRACT.md      v1.0, DRAFT — Tier 0 Bootstrap RBAC read-only API
│   │                                   contract: 4 endpoints (`health`, `roles`,
│   │                                   `permissions`, `roles/{pk}/permissions`) over 3 tables
│   │                                   (`role_master`/`permission_master`/`role_permission`)
│   ├── FOUNDATION_API_CONTRACT.md     v1.1, DRAFT — Tier 1 Foundation read-only API
│   │                                   contract: 17 endpoints across 11 tables, conventions
│   │                                   (query-param filtering, hierarchical drill-down, code
│   │                                   lookups, no pagination in Tier 1), full endpoint
│   │                                   catalogue with example responses, response-schema
│   │                                   summary, error table, implementation file map
│   └── ORGANIZATION_API_CONTRACT.md   v1.2, DRAFT — Tier 2 Organization read-only API
│                                       contract: 7 endpoints (`types`, `statuses`,
│                                       `organizations` list/detail/children, `children-stats`,
│                                       `hierarchy`) over 1
│                                       table plus Foundation `master_data`, carrying forward Tier 0/1's conventions plus the
│                                       recursive-CTE `/hierarchy` pattern and (v1.2) the FAM-036
│                                       majority-rule aggregate-stats endpoint
├── standards/
│   └── lifecycle/         SOL-LIFE-001 (PARTICIPATION_LIFECYCLE_RULES.md), SOL-LIFE-002 (PERSON_LIFECYCLE_RULES.md), both FROZEN v1.0.0 — a SOLUTION-layer standards path distinct from the governance-layer docs/00_Project_Governance/STD/, not yet cross-referenced from either README or from the Sevak/Mahila/Kumari module docs that should cite SOL-LIFE-001 (see Gotchas)
├── architecture/
│   ├── README.md
│   ├── GETTING_STARTED.md              New (Tier 4) — setup guide overlapping with root
│   │                                    `README.md`'s Getting Started section and this file's
│   │                                    Setup & running section; currently the most current of
│   │                                    the three (verified against actual `02_build.sh`/
│   │                                    `pytest.ini`/`api/main.py` at time of writing)
│   ├── TECH_STACK_DECISIONS.md        v1.3 — approved SOLUTION-layer tech decision; Django-to-FastAPI
│   │                                   migration (FastAPI is now the sole backend framework, no ORM);
│   │                                   Mobile Strategy (`TECH-MOB-001`, FROZEN — Flutter Android+iOS
│   │                                   replaces PWA-first/Capacitor) — see Architecture section above
│   ├── DEVELOPER_REFERENCE_GUIDE.md   per-module "which doc to read before coding" matrix
│   ├── PROGRAMME_EVENT_DOMAIN_MODEL.md         (`SOL-EVT-001`) — domain model for Programmes & Events, feeding the `programmes_events` module
│   ├── EVENT_ENTITY_RECONCILIATION.md          (`SOL-EVT-002`) — reconciles that domain model against UPBS/Kishor/Sevak/Mahila/Finance/Attendance's own event-shaped entities
│   ├── MODULE_DEPENDENCY_MAP.md                (`SOL-ARCH-007`) — dependency map (hard FK/runtime/domain integrations), PROPOSED not frozen (v0.1.0); its §3 inventory table now lists all 22 modules (incl. Assets & Property), matching its own status footer — the prior 21-vs-22 inconsistency was fixed by commit `1d96fb1`
│   ├── IMPLEMENTATION_DEPENDENCY_ORDER.md      (`SOL-ARCH-008`), `IMPLEMENTATION-TIER-001` — unified 0–13 build order across all 22 modules, FROZEN (Organization Tier 2, Person Tier 3, Heritage Tier 7, Programmes & Events Tier 8, Finance Tier 12; Assets & Property in Tier 6). §79's status footer carries the unified tier model (FROZEN/v1.0.0/22-modules); its non-normative implementation-status note tracks that Tiers 0-6 are implemented/in progress (see "Current position" above)
│   ├── PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md (`SOL-EVT-006`), v1.1.0, FROZEN — final compatibility review for Module #21 against every other module; no hard conflicts; open ownership/migration-strategy risks it originally flagged were resolved by the file below
│   ├── CROSS_MODULE_PRINCIPLES.md              (`ARCH-CROSS-001`), v1.1.0, FROZEN — project-wide principles: one-owner-per-table, cross-module reference not duplication, Finance sole-owner of financial transactions, `DOC-ARCH-001` (document_master + field_change_log → Foundation), Correspondence Register decision. Carries 3 explicitly PENDING (not frozen) DDL-phase design notes: org short code, local Sakha number format, Visitor vs. Approved Darshak threshold
│   ├── FK_DEPENDENCY_GRAPH.md                  (`SOL-ARCH-009`), FROZEN — physical FK dependency graph ("Gate 8") across 86 frozen tables, topologically sorted into 8 depths, zero cycles; resolves the audit-actor circular-dependency problem via a two-pass DDL strategy
│   ├── DDL_CREATION_ORDER.md                   (`SOL-ARCH-010`), FROZEN — the exact numbered `CREATE TABLE` sequence for all 86 tables ("Gate 9") plus the Pass-2 deferred-constraint list
│   ├── BOOTSTRAP_ARCHITECTURE.md               (`SOL-ARCH-011`), FROZEN — Phase 0: creates/seeds `role_master`/`permission_master`/`role_permission` (zero FK deps) before Foundation; defines `nss_db_owner` (PostgreSQL DDL owner) ≠ `NSS_ERP_ADMIN` (ERP RBAC role); does not change SOL-ARCH-010's depth/sequence or claim table ownership (stays with Administration). Permission catalogue, bootstrap-admin Sangha Sevi identity, and MFA-controlled DB access (future `SOL-ARCH-012`) remain PENDING
│   └── PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md (`SOL-EVT-007`), FROZEN — closes all 7 P&E cross-module reconciliation gates; freezes `P&E-ARCH-001`/`002`; candidate table set settled at 7
├── code_explanations/      Per-layer "requirement + line-by-line" code catalogues — moved out
│                          of `architecture/code_explanations/` into this dedicated top-level
│                          folder (one level up, out of `architecture/`; see the Gotcha on this
│                          move below):
│                          API_CODE_EXPLANATIONS.md, DATABASE_CODE_EXPLANATIONS.md,
│                          UI_CODE_EXPLANATIONS.md, SECURITY_CODE_EXPLANATIONS.md,
│                          TESTING_CODE_EXPLANATIONS.md (updated for Tier 4
│                          Family + Membership). Security audit reports (`TIER0_SECURITY_AUDIT.md`
│                          through `TIER4_SECURITY_AUDIT.md`) used to live here too, but moved to
│                          `docs/03_Solution/security/` as part of the Tier 4 work — see below;
│                          code_explanations/README.md now indexes only the 5 per-layer docs
├── database/
│   └── DATABASE_DESIGN_STANDARDS.md   (`SOL-DB-001`, DRAFT — SOURCE ALIGNED Consolidation) — cross-module DB conventions consolidated from module table-design docs: `_pk` UUID PK convention, audit columns, soft-delete, master-data architecture (generic `master_category`/`master_data` vs domain masters), module ownership boundaries (one owning module per table), cross-module FK principles, DDL build order sketch. **States a `_id` business-identifier convention (`person_id`, `organization_id`, `sangha_sevi_id`) that contradicts the project's already-frozen `_code`-only convention** — see Gotchas/Open questions
├── security/
│   ├── SECURITY_ARCHITECTURE.md       (`SOL-SEC-001`, DRAFT — SOURCE ALIGNED Cross-Reference) — routing map only, no new rules: STD-05 (policy) → Authentication (identity/credentials) → Administration (RBAC) → Audit (logging) → per-module business rules (column-level sensitive-data handling); explicitly does not duplicate any rule already defined elsewhere
│   ├── TIER0_SECURITY_AUDIT.md (v1.1, Complete — 10 passed, 1 fix applied, 6
│   │   advisory [4 resolved/1 partial/1 N/A]), TIER1_SECURITY_AUDIT.md (v1.1,
│   │   Complete — 9 passed, 6 advisory [3 resolved/1 partial/1 advisory/1
│   │   N/A]), TIER2_SECURITY_AUDIT.md (Tier 2 Organization),
│   │   TIER3_SECURITY_AUDIT.md (Tier 3 Person), and TIER4_SECURITY_AUDIT.md (Tier 4 Family +
│   │   Membership — 18 checks passed, 0 fixes required, 3 of 5 advisory items resolved) —
│   │   moved here from `docs/03_Solution/code_explanations/` as part of the Tier 4 work
│   └── SECURITY_AUDIT_TIER0_4.md      New consolidated summary across all five tier audits
├── infrastructure/
│   └── DEPLOYMENT_SYNC_PLAN.md        Deployment/repository-sync plan
└── ui/
    ├── README.md
    └── mockups/           13 static HTML screens (Tailwind CSS + DaisyUI via CDN, no build step) + README.md; visual targets for Phase 4, not functional prototypes
```

`docs/03_Solution/api/` and `docs/03_Solution/code_explanations/` are both distinct from the
real, implemented FastAPI code at the root-level `api/` — the former holds request/response
contracts, the latter holds line-by-line narration of the same code; neither is the code itself.

`docs/03_Solution/modules/attendance/DARSHAK_BUSINESS_RULE.md` records an ERP implementation
decision (not derived from the Bye-Law): an earlier project Rule Book used "Darshak" as an
informal membership tier, but the actual Bye-Law (`REF-002`) has no such category — only
Probationary/Regular/Associate. "Darshak" is corrected to mean, operationally, either a
Probationary Member or a Regular Member visiting from another Sakha; it may appear as a UI
display label (dashboards, attendance screens) but must never be a `membership_type_master`
value in the database.

**Doc/code gap.** Membership, family, attendance, heritage, kumari, kishor, mahila, sevak,
administration, audit, authentication (Solution-layer), backup_technical, governance
(Solution-layer), publications, reports, upbs, finance, programmes_events, person, and
assets_property all have Solution-layer design docs describing schemas richer than what exists
in code — none has any corresponding API/backend implementation at all (Person's DDL exists but
has no API — see Key Workflow #3). **Foundation and Organization are now the exceptions**:
Foundation's Solution-layer design (10 tables described) is not just implemented in SQL (12
tables, see above) but also has a full read-only API (`api/routers/foundation.py`, 17 endpoints)
and verification UI (originally `frontend/foundation.html`, now `admin.html`'s Reference Data and
Geography tabs); Organization's Solution-layer design (3 tables)
is **no longer** matched 1:1 in SQL — only 1 physical table (`organization`) remains, with type/
status now sourced from Foundation's `master_data` (see Key Workflow #4 and Gotchas) — but it
still has a full read-only API
(`api/routers/organization.py`, 7 endpoints) and verification UI
(originally `frontend/organization.html`, now `admin.html`'s Organizations and Organization
Hierarchy tabs) — both are complete DB→API→UI vertical slices, released as
v0.7.0 (Foundation) and v0.8.0 (Organization). The only other implemented API surface in the codebase is the Tier 0
bootstrap-RBAC router (`api/routers/bootstrap.py`), which isn't one of the 22 Solution-layer
modules listed above. Don't assume any other Solution-layer doc describes currently running
code.

## Setup & running

Setup is documented in `database/README.md` and `database/scripts/README.md`; the steps below
summarize the full sequence from a clean machine to a running API.

1. **Python dependencies** (repo root):
   ```
   python3 -m pip install -r requirements.txt   # macOS/Linux
   py -m pip install -r requirements.txt         # Windows
   ```
   `requirements.txt` lists FastAPI, Uvicorn, psycopg2-binary, Pydantic, python-dotenv,
   `slowapi`/`limits`/`wrapt` (rate limiting), `argon2-cffi`/`PyJWT` (Tier 5 auth), and the
   Playwright test stack (`pytest-playwright`, `playwright`, `pytest-base-url`, `greenlet`),
   plus their transitive dependencies (Starlette, anyio, click, h11, idna, colorama, etc.) — no
   Django. It's plain UTF-8 text (a prior UTF-16LE Windows-migration artifact was fixed).

2. **Database (raw-SQL track):** the bootstrap sequence is documented in
   `database/scripts/README.md` and `docs/03_Solution/architecture/GETTING_STARTED.md`:
   1. `00_create_database.sql` (as superuser on `postgres` DB) — creates the `nss_erp` database
      and the `nss_db_owner`/`nss_db_backend`/`nss_db_writer` roles (all `LOGIN`, no password).
   2. `01_extensions.sql` (as superuser on `nss_erp`) — installs pgcrypto, pg_trgm, btree_gin,
      postgis; creates the `nss` schema owned by `nss_db_owner`.
   3. `06_setup_env.sh` (superuser, bash only) — prompts for and sets all three role passwords
      and writes `api/.env` (including a random `JWT_SECRET_KEY`). On Windows set the passwords
      with `ALTER ROLE` and write `api/.env` by hand.
   4. `02_build.sh` / `.ps1` (as `nss_db_owner`) — runs `pip install -r requirements.txt`, then
      all DDL + seed in Phases 0-14 (Bootstrap RBAC → Foundation → Organization → Person →
      Family → Membership → grants → Authentication → Administration → admin bootstrap →
      Audit). The seed includes the all-India geography bulk files, so Phase 2 is slow. Re-runs
      are idempotent: `02_build.sh` is existence-gated per table (`run_ddl`/`run_seed`,
      `to_regclass`; existing table → DDL and seed skipped, `[EXISTS]`), `.ps1` uses `[SKIP]` on
      "already exists"/duplicate key. See `GETTING_STARTED.md` §7a-2.
   5. `03_validate.sh` / `.ps1` (as `nss_db_owner`) — post-build checks (table existence, row
      counts as minimums, unique constraints, FK integrity).

   `04_grant_backend.sql` (Phase 9) and `05_create_writer_role.sql` (Phase 12) are run by
   `02_build.sh` itself. The build covers **48 tables** (3 Bootstrap RBAC + 15 Foundation + 1
   Organization + 2 Person + 6 Family + 14 Membership + 5 Authentication + 2 Administration).
   `02_build.ps1` matches `02_build.sh` v2.6 in phase/file order (incl. `post_office`, the `08c` seed and Phase 7b) and in the existence-gate mechanism (`Invoke-Ddl`/`Invoke-Seed`).
   `03_validate.sh`/`.ps1` only WARN on stale minimums (`master_data` 82 vs 89
   seeded, etc.) and have no Family/Membership/`system_event_log`/`credential_sequence_counter`
   checks. A fresh build seeds no demo Person/Family/Membership data.

3. **API environment file:** create `api/.env` (read via `python-dotenv`'s `load_dotenv()` at
   `api/config.py` (top of file), which resolves the path as `Path(__file__).resolve().parent / ".env"`
   — i.e. `api/.env`, not a repo-root `.env`) with:
   ```
   DB_NAME=nss_erp
   DB_USER=nss_db_backend
   DB_PASSWORD=...       # the password you set for nss_db_backend in step 2
   DB_HOST=localhost
   DB_PORT=5432
   DB_WRITE_USER=nss_db_writer        # Tier 5 (write pool)
   DB_WRITE_PASSWORD=...
   JWT_SECRET_KEY=...                 # Tier 5 (no default)
   ```
   `DB_NAME`, `DB_USER`, `DB_PASSWORD` are required with no defaults — `Settings.validate()`
   (`api/config.py`) raises `RuntimeError` listing any that are missing. `DB_HOST`
   defaults to `localhost`, `DB_PORT` to `5432` if omitted. `Settings.validate_auth()` additionally
   requires `JWT_SECRET_KEY`/`DB_WRITE_USER`/`DB_WRITE_PASSWORD`; `06_setup_env.sh` generates all
   of these.

4. **Start the API** (from the **repository root**, not from `api/`):
   ```
   python3 -m uvicorn api.main:app --reload --port 8001   # macOS/Linux
   py -m uvicorn api.main:app --reload --port 8001         # Windows
   ```
   Swagger UI: `http://localhost:8001/docs` (disable via `DISABLE_DOCS=true`/`1`/`yes` in
   `api/.env`, which also disables `/redoc` and `/openapi.json`). Pages: `/` redirects to
   `/login`; `/login`, `/register`, `/dashboard`, `/admin` are served from `frontend/` through
   `_serve_page()` (each registered only if its HTML file exists). The six standalone Tier 0-4
   verification pages were deleted — their functionality lives in `admin.html` and
   `dashboard.html`. Only `bootstrap.py` (4 endpoints) and the public `/api/v1/register` and
   `POST /api/v1/auth/login|refresh|forgot-password|reset-password` endpoints are reachable
   without a JWT; everything else is gated per router (see `CLAUDE.md` → Architecture and
   `docs/03_Solution/api/API_CONTRACT.md`, which lists the 137 v0.11.0 endpoints across 12 routers (Tier 6 raises the total to 201 across 15; not yet in that file) with
   their gates).

5. **Run the tests** (from the repository root, once the database is built per step 2 and
   `api/.env` per step 3):
   ```
   pytest                    # all tests (api + db + ui + security)
   pytest -m integration     # tests/api/ + tests/db/ + tests/security/
   pytest -m ui               # tests/ui/ (Playwright browser tests)
   pytest tests/api/test_bootstrap.py     # Tier 0 only
   pytest tests/api/test_foundation.py    # Tier 1 only
   pytest tests/api/test_organization.py  # Tier 2 only
   pytest tests/api/test_person.py        # Tier 3 only
   pytest tests/api/test_family.py        # Tier 4 only
   pytest tests/api/test_membership.py    # Tier 4 only
   pytest tests/security/test_security_headers.py # cross-tier security middleware only
   pytest tests/db/test_data_integrity.py # cross-module smoke tests
   pytest tests/api/test_auth.py tests/api/test_admin.py tests/api/test_registration.py \
       tests/api/test_forgot_password.py  # Tier 5
   pytest tests/ui/                       # Playwright browser tests 
   pytest tests/api/test_family.py::TestOrgAdminFamilyFilter::test_filter_by_sakha_code  # one test
   ```
   Configured via `pytest.ini` (repo root: `testpaths = tests`, `integration`/`ui`/`db` markers
   — the Tier 5 added `ui` and `db` alongside the original `integration`).
   `tests/conftest.py`'s `client` fixture wraps `fastapi.testclient.TestClient(app)` against the
   **real** local Postgres DB set up in step 2 — nothing is mocked, so these are true
   integration tests, not unit tests. On the Tier 5, `conftest.py` was rewritten to hold
   one session-scoped `nss_db_writer` connection for the whole run, wrapping each test *module*
   in a `SAVEPOINT` that's rolled back at teardown — both `get_connection`/`get_write_connection`
   dependencies are overridden to yield that same connection, so tests no longer depend on any
   pre-seeded demo data (which was deleted on this branch — see Tier 5 above). The same branch
   also split `tests/` from a flat `test_*.py` package into `tests/api/`, `tests/db/`,
   `tests/security/` and a Playwright `tests/ui/` (file lists and counts: `tests/README.md`; the UI
   tests need Playwright browsers installed and a running app). `pytest` and
   `httpx` (required by `TestClient` at import time) are pinned in `requirements.txt`. No lint/
   format tooling is configured yet.

**Tier 5 additions to the bootstrap sequence (v0.11.0):** after Phase 9 (grant `nss_db_backend`) above,
`02_build.sh`/`.ps1` continue with Phase 10 (Authentication DDL — `user_account`,
`password_history`, `registration_claim`, `password_reset_token`), Phase 11 (Administration DDL
— `user_role`, `admin_scope`), Phase 12 (`database/scripts/05_create_writer_role.sql` — grants
`nss_db_writer` schema `USAGE` + `SELECT` + `INSERT`/`UPDATE` on every `nss` table, present and
future; no `DELETE`/DDL), Phase 13 (`python3 scripts/bootstrap_admin.py` — seeds a single admin superuser,
login `SS1` or `P1`, default password `Admin@123`, `force_password_change=FALSE`; run as a Python
script rather than plain SQL because the password hash must be generated at runtime with the
app's own Argon2 hasher, never hardcoded), and Phase 14 (`14_system_event_log.sql` +
`15_audit_trigger.sql` — the `nss.system_event_log` audit table plus a `fn_audit_trigger()`
attached to every `nss.*` table via a `DO $$` loop, confirmed wired into `render_build.sh`).
**`01_admin_bootstrap.sql` had a silent membership-type bug, now fixed (Tier 5):** it used
to pick "first active `MEMBERSHIP_TYPE` by `display_order`", which happened to be
`PROBATIONARY`/"Darshaka" (`display_order=1`, lower than `REGULAR`'s `2`) — seeding the admin
superuser as a Darshaka instead of a regular member. The seed now selects `REGULAR` explicitly
(the earlier corrective `UPDATE` was dropped in seed v2.0, so a database seeded by the buggy version must be repaired by hand or rebuilt).
`database/scripts/06_setup_env.sh` is a new
convenience script (superuser) that sets passwords on all three PostgreSQL roles
(`nss_db_owner`/`nss_db_backend`/`nss_db_writer`) and generates `api/.env` with matching
credentials plus a random `JWT_SECRET_KEY`, run once after `00_create_database.sql`. `api/.env`
additionally needs `DB_WRITE_USER=nss_db_writer`, `DB_WRITE_PASSWORD=...`, and
`JWT_SECRET_KEY=...` before any `/api/v1/auth/*` or `/api/v1/admin/*` endpoint will work —
`Settings.validate_auth()` raises if any of the three is missing, but only the write-pool-backed
endpoints call it, so the Tier 0-4 read-only endpoints still start up fine without them.
**Also on this branch:** `database/README.md` and `database/scripts/README.md` were both
previously stale and disagreed with each other and with the actual `02_build.sh` — both are now
fixed as of this documentation pass (`database/scripts/README.md`'s Phase 13 description now
correctly points to `scripts/bootstrap_admin.py` against
`database/seed/04_admin/01_admin_bootstrap.sql`, and `database/README.md` now reflects all Tier 5 tables and the 47-table total).

**Deployment (Render.com):** `render.yaml` (repo root) is Render's Infrastructure-as-Code
manifest — defines a single free-tier web service running `uvicorn api.main:app --host 0.0.0.0
--port $PORT`. It does **not** define a managed Render Postgres database service:
`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` (plus an apparently-unused
`DATABASE_URL` — `api/config.py` only reads the five individual vars, never a connection-string
env var) are declared as `sync: false` env vars that must be set manually in the Render
dashboard, pointing at an external Neon.dev PostgreSQL instance (per `TECH_STACK_DECISIONS.md`
§1/§6) — not provisioned by this file. `render_build.sh` runs on every deploy: `npm install` + the
Tailwind CLI build, `pip install -r requirements.txt`; the DB bootstrap below runs on every deploy.
`RUN_DB_BOOTSTRAP` (`true`/`1`/`yes`/`on`, case/whitespace-insensitive; default off; see
`docs/03_Solution/architecture/DEPLOYMENT_PROCEDURE.md`) gates **only** the Phase 13 admin seed
(an earlier version gated the whole bootstrap; corrected 2026-10-05). The bootstrap does `CREATE SCHEMA IF NOT EXISTS nss`, sets the
database `search_path`, best-effort installs `pgcrypto`/`pg_trgm`/`btree_gin` (some may be
unavailable on Neon's free tier; `postgis` isn't attempted), creates the three `nss_db_*` roles,
and runs the same phases as `database/scripts/02_build.sh` (v2.6 phase order, including `post_office`,
`08c` and Phase 7b) directly via `psql`. There is no "already bootstrapped" early exit: every
phase runs on every deploy. Table DDL/seeds are existence-gated (`run_ddl`/`run_seed`,
`to_regclass`, header "Version 3.0"): a table that already exists has its DDL and seed skipped,
only new tables are created and seeded; non-table objects (`run_sql`) still report `[SKIP]` on
"already exists"/duplicate-key. A Phase 13 (admin bootstrap) failure only warns. Treat the Render setup as declared-but-unverified infrastructure (notably whether
`npm install` works in a `runtime: python` service).

## Configuration

| Setting | Source | Notes |
|---|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `api/.env` (not committed, no `.env.example`) | Required, no defaults — `Settings.validate()` raises `RuntimeError` if any is missing |
| `DB_HOST` | `api/.env` | Defaults to `localhost` if unset |
| `DB_PORT` | `api/.env` | Defaults to `5432` if unset |
| `API_PORT` | `api/.env` | Defaults to `8001` — defined but currently unread; the actual port is hardcoded in the `uvicorn` run command instead, so the two can silently drift if one changes without the other |
| `DISABLE_DOCS` | `api/.env` | Defaults to `false`; when truthy (`1`/`true`/`yes`), disables `/docs`, `/redoc`, and `/openapi.json` on the FastAPI app (`api/main.py`) |
| `CORS_ORIGINS` | `api/.env` | Comma-separated allowed origins; defaults to empty, in which case `CORSMiddleware` is never registered at all (no CORS headers on any response) |
| `RATE_LIMIT` | `api/.env` | Defaults to `"60/minute"` (a `slowapi`/`limits`-style rate spec); applied globally via `SlowAPIMiddleware`, not per-route |

**Tier 5 additions (v0.11.0):**

| Setting | Source | Notes |
|---|---|---|
| `DB_WRITE_USER`, `DB_WRITE_PASSWORD` | `api/.env` | Credentials for the `nss_db_writer` pool; required only by write-path endpoints — `Settings.validate_auth()` raises if missing, called lazily by `get_write_pool()` |
| `JWT_SECRET_KEY` | `api/.env` | No default — required for any `/api/v1/auth/*`/`/api/v1/admin/*` endpoint; `JWT_ALGORITHM` is hardcoded `HS256` (not env-configurable) |
| `JWT_ACCESS_TOKEN_MINUTES` / `JWT_REFRESH_TOKEN_DAYS` / `JWT_ABSOLUTE_SESSION_DAYS` | `api/.env` | Default `30` / `7` / `30` — access-token TTL, refresh-token TTL, and the hard session ceiling enforced in `decode_token()` regardless of how many times a refresh token is used |
| `DB_READ_POOL_MIN`/`MAX`, `DB_WRITE_POOL_MIN`/`MAX` | `api/.env` | Default `2`/`15` and `1`/`5` — psycopg2 `ThreadedConnectionPool` sizing for the two pools |
| `MAX_FAILED_ATTEMPTS` / `LOCKOUT_DURATION_SECONDS` | hardcoded in `Settings`, not env-configurable | `5` attempts → `30`-second auto-unlock |
| `PASSWORD_MIN_LENGTH`/`MAX_LENGTH`/`EXPIRY_DAYS`/`EXPIRY_WARNING_DAYS` | hardcoded in `Settings` | `8`/`128`/`365`/`30` |
| `RESET_OTP_LENGTH`/`EXPIRY_MINUTES`/`MAX_ATTEMPTS`/`RATE_LIMIT_MINUTES` | hardcoded in `Settings` | `6`-digit OTP, `15`-minute expiry, max `3` active tokens, `60`-minute rate window |
| `CSP_ENABLED` / `CSP_REPORT_ONLY` | `api/.env` | Default `true` / `false` — emit the Content-Security-Policy (as `-Report-Only` when the second is truthy); `script-src` has no `'unsafe-inline'`, so pages may not use inline event handlers |
| `CSP_SCRIPT_SRC_EXTRA` / `CSP_STYLE_SRC_EXTRA` | `api/.env` | Comma-separated extra CSP origins (e.g. a new CDN) without a code change |
| `DEBUG_MODE` | `api/.env` | Defaults to `false`; when truthy, `POST /api/v1/auth/forgot-password` echoes the generated OTP back in the response body (`otp_debug`) instead of only logging/emailing it — a deliberate development-only escape hatch, remove once email/SMS delivery exists |

No other configuration surface (feature flags, external service credentials, `ALLOWED_HOSTS`,
etc.) exists in the code.

## Key workflows

### 1. Health check → DB connectivity
`GET /api/v1/bootstrap/health` (`api/routers/bootstrap.py:27-39`) calls `check_connection()`
(`api/database.py:63-80`), which grabs a connection from the `psycopg2` pool, runs `SELECT 1`,
and returns it — swallowing all exceptions so no credentials/error detail ever leak to the
client. The endpoint returns `{"status": "ok"/"degraded", "database": "connected"/
"unreachable"}`. This is the only endpoint that doesn't use the `Depends(get_connection)`
pattern the other three use.

### 2. Roles / permissions lookup
`GET /api/v1/bootstrap/roles` (`api/routers/bootstrap.py:42-68`) runs
`SELECT role_master_pk, role_code, role_name, role_class, scope_level, description,
display_order, is_active FROM nss.role_master WHERE is_active = TRUE ORDER BY display_order`
via `Depends(get_connection)`, returning the 10 frozen roles as `RoleResponse` models.
`GET /api/v1/bootstrap/permissions` mirrors this against `nss.permission_master` — was empty
through Tier 4; **now returns real rows in Tier 5 (v0.11.0)**, since
`permission_master`/`role_permission` are now seeded (see Bootstrap RBAC above).
`GET /api/v1/bootstrap/roles/{role_pk}/permissions` (`api/routers/bootstrap.py:100-152`) first
verifies the role exists and is active (404 if not), then joins `nss.role_permission` to
`nss.permission_master` for that role (same — no longer empty for roles with real mappings).
All three endpoints are unauthenticated, read-only, and connect as `nss_db_backend`
— they exist to verify the RBAC schema is queryable, not to enforce RBAC themselves.

### 3. Person business-ID generation (now wired to real write paths in Tier 5)
`database/ddl/01_foundation/04_id_sequence_master.sql` defines an `id_sequence_master` table —
a registry of `{sequence_code, prefix, current_value, padding_length}` rows, seeded with **14**
sequences (`database/seed/01_foundation/03_id_sequence_master.sql`): `PERSON`→`P` (padding
**10** — first code is `P0000000001`, 11 characters), `SANGHA_SEVI`→`SS`, `ANCHALIKA`→`ANC`,
`ZILLA`→`ZL`, `SAKHA`→`SKH`, `SAKHA_ASANA`→`SA`, `PATHA_CHAKRA`→`PC`, `PARIBARIK_ASANA`→`PA`,
`PARIBARIK_SANGHA`→`PS`, `FAMILY`→`F`,
`DOCUMENT`→`DOC`, and — added in Tier 5, for the 3 new Tier 4 org types —
`KUMARI_SANGHA`→`KS`, `SEVAK_SANGHA`→`SEV`, `MAHILA_SANGHA`→`MS` (all padding 8 except `PERSON`,
and `PARIBARIK_ASANA`/`PARIBARIK_SANGHA`/`KUMARI_SANGHA`/`SEVAK_SANGHA`/`MAHILA_SANGHA` at
5/3/5/5/5 respectively). The org-type-specific prefixes now cover **10** organization types
(all 13 `ORGANIZATION_TYPE` values except the 3 apex/singleton ones — `KENDRA`,
`NILACHALA_KUTIRA`, `SMRUTI_MANDIRA` — which don't mint sequence-numbered codes). This produces IDs for the `person.person_id` column
(`database/ddl/03_person/02_person.sql`, real implemented DDL as of Tier 3 —
`person_id VARCHAR(20) NOT NULL UNIQUE`, `uq_person_id`) — the column name now matches the
Person module design doc (`docs/03_Solution/modules/person/05_person_table_design.md`, v1.0.0
SOURCE ALIGNED), resolving the earlier `person_code`/`person_id` naming disagreement. Person has
**no seed data** (`database/scripts/03_validate.sh` checks table existence and zero row counts,
not FK integrity against seeded rows) — `tests/api/test_person.py` is skip-guarded wherever it needs
an actual row (via a `_get_first_person_pk`-style helper), since a fresh build seeds zero
demo Person rows. **This is no longer pure configuration waiting on a write path: `api/helpers.py
::next_id(cur, sequence_code)` (Tier 5) does an atomic `UPDATE ... RETURNING`
against `id_sequence_master` and is called from `api/routers/registration.py` (self-registration
→ `PERSON`), `api/routers/admin.py` (admin-created persons/orgs → `PERSON` + the org-type
sequences), and `api/routers/claim_approval.py` (`approve_claim()` → `SANGHA_SEVI`)** — resolving
the previous "no function/trigger/API code does this yet" gap. `FAMILY`'s sequence is
similarly consumed by `family.py::create_family()` to mint `family_id` (`F1`, `F2`, ...). As of
Tier 4, business-identifier examples use unpadded values (`P1`, `SS1`, not `P0000000001`) even
though `PERSON`'s own `padding_length` is still seeded at 10 — `id_sequence_master.padding_length`'s
CHECK constraint was loosened to allow `0`, and the sequences that matter for the unpadded
convention (`SAKHA`, org-type sequences) are seeded at `padding_length = 0`; `PERSON`'s row is a
historical holdover from before that decision and hasn't been changed to match.

### 4. Organization — hierarchy, reference data, contact fields (DB + API implemented, Tier 2)
`docs/03_Solution/modules/organization/01_organization_module_overview.md` through
`05_organization_table_design.md` (v1.1.0, GOVERNANCE ALIGNED) specify a self-referencing
`organization` table plus `organization_type_master` and `organization_status_master` — three
tables only, address inline on `organization` (no separate `organization_address` table).
**The specific Kendra → Anchalika/Zilla → Sakha → Patha_Chakra type-to-type parent matrix is
explicitly NOT frozen** — the business rules doc's §22 "Rules Explicitly Not Assumed" lists
both the exact parent-compatibility matrix and the exact `organization_type_master` seed values
as open items; only the generic apex + self-referencing structure is frozen. **As implemented,
this 3-table design has been superseded**: `database/ddl/02_organization/` now defines only the
`organization` table itself. The former `organization_type_master`/`organization_status_master`
tables were retired and their rows migrated into Foundation's generic `master_data` (categories
`ORGANIZATION_TYPE`, `STATUS`), matching the project's frozen "Master Data Driven" principle but
no longer matching this module's own frozen v1.1.0 table design. Anyone picking up further
organization work should treat the design docs as the historical target, not the current
physical schema — see Gotchas for the full reconciliation status (this diverges from
`FK_DEPENDENCY_GRAPH.md`, `DDL_CREATION_ORDER.md`, and the Governance Baseline's naming/master-
data-catalogue docs too, none of which have been reconciled with this migration).

**API now implemented.** `api/routers/organization.py` (prefix `/api/v1/organization`) exposes 8
GET endpoints (gated by `require_permission("ORGANIZATION_VIEW")` in Tier 5 — its own module docstring says "7 GET endpoints," now stale again since the new
`/stats` endpoint below shipped without an accompanying docstring update) — the
same raw-`psycopg2`/`Depends(get_connection)` pattern as Tier 0/1.
Grouped by theme:
- **Reference:** `/types`, `/statuses` — both now query Foundation's `nss.master_data` joined to
  `nss.master_category`, filtered by `category_code = 'ORGANIZATION_TYPE'` (13 active values) /
  `'STATUS'` respectively — no longer the
  dedicated `organization_type_master`/`organization_status_master` tables. `/statuses`
  additionally filters by a newer `applicable_modules` column (added on top of Tier 4, see Key
  Workflow #6) so it returns only the 7 Organization-applicable values out of the category's
  16 total, not the full unified list. The response model
  for `/statuses` was renamed `StatusResponse` (from `OrganizationStatusResponse`) to reflect
  that it's no longer organization-specific.
- **Core:** `/organizations` (optional `type_code`/`status_code` filters),
  `/organizations/{organization_pk}` (404 if missing),
  `/organizations/{organization_pk}/children` (404 if the parent itself doesn't exist, then
  direct children only) — all three share one SQL fragment (`_ORG_SELECT`) that joins
  `organization` to `master_data` (via `organization_type_master_data_pk`/
  `status_master_data_pk`) for type/status and LEFT JOINs the self-referencing parent plus
  Foundation's `district`/`state`/`country`/`city_village`/`postal_code` tables (address fields
  are nullable, hence LEFT JOIN).
- **Aggregate stats (added on top of Tier 4):** `/organizations/{organization_pk}/children-stats`
  — for each direct child, recursively walks all descendant Sakhas and returns
  `OrgChildStatsResponse` (family/member/person counts), reusing the "effective Sakha"
  majority-rule CTE Family's `/sakha-alignment` implements — **now a single shared
  `FAMILY_MAJORITY_CTE_SQL` constant in `api/helpers.py` (Tier 5), not a duplicated
  byte-for-byte copy.** **This recursive CTE still has
  no depth-cap guard**, unlike `/hierarchy` below (`t.depth < 10`) — a circular parent reference
  could recurse indefinitely; this is a real, still-open gap (see Gotchas/Deferred Items), not
  fixed by the CTE-sharing above. Its own docstring claims it's "used by the org admin sidebar to
  display inline counts on each drill-down card," and while no such consumer exists in
  `frontend/admin.html`/`admin.js`'s Organization Hierarchy tab (which absorbed the deleted
  `organization.html`/`organization.js`), the endpoint **is now consumed** (Tier 5) —
  `frontend/assets/js/dashboard.js`'s `_fetchOrgChildrenStats(orgPk)` calls it from the org
  family browser inside `dashboard.html`'s Family tab instead, a different page than the
  docstring implies but no longer an unwired endpoint.
- **Aggregate stats (new in Tier 5, Tier 5):** `/organizations/{organization_pk}/stats` — the
  same recursive descendant-Sakha counting as `/children-stats` above (sharing the same
  `FAMILY_MAJORITY_CTE_SQL` constant), but collapsed to a single `OrgStatsResponse` row of
  whole-subtree totals for the *requested* org itself (not its children). 403s if the requested
  org falls outside the caller's own admin scope (ADMIN-BR-076) rather than the viewer's own
  scope, unlike `/api/v1/admin/dashboard-stats` — this is what lets it render the new Org
  Dashboard tab (`frontend/assets/js/org-dashboard.js`) correctly no matter which org the viewer
  drilled into. Covered by `tests/security/test_organization_stats_security.py`.
- **Navigation:** `/hierarchy` — a `WITH RECURSIVE org_tree` CTE (anchor:
  `parent_organization_pk IS NULL`; recursive leg joins `t.organization_pk =
  o.parent_organization_pk`, tracking `depth`, capped at `depth < 10`), returned as a flat list ordered by `depth,
  organization_name` — the UI reconstructs the tree client-side rather than receiving nested
  JSON. The deleted `organization.js` did this with a `depthIndent(depth)` indent helper; its
  successor, `frontend/admin.html`'s Organization Hierarchy tab, instead renders one drill level
  at a time from the same flat list (`admin.js`'s `orgChildrenOf()`/`orgLevelNodes()` filtering
  on `parent_organization_pk`, with a breadcrumb `orgDrillPath`).

`OrganizationResponse` (`api/schemas/organization.py`) additionally resolves 8 contact/
online-presence columns recently added to the DDL: `phone_number`/`mobile_number` (nullable),
`email` (required, DB default `info@nsspuri.org`)/`org_email` (nullable), `website_url`
(required, DB default `https://www.nsspuri.org`)/`org_website_url` (nullable), and
`youtube_channel_url` (required, DB default
`https://www.youtube.com/@NilachalaSaraswataSangha`)/`org_youtube_channel_url` (nullable) — the
NSS-wide defaults are always populated, the org-specific overrides are always nullable.
`OrganizationHierarchyNodeResponse` is deliberately leaner (no contact/geography fields) to match
`/hierarchy`'s narrower SQL. Full contract in `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md`;
line-by-line walkthrough in `docs/03_Solution/code_explanations/API_CODE_EXPLANATIONS.md`.

**ORG-BR-099 narrowed (governance decision 2026-09-28):**
`ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`PATHA_CHAKRA` may never carry a physical premises address
(`address_line_1`/`address_line_2`/`city_village_pk`/`postal_code_pk`/`latitude`/`longitude` —
DB-trigger-enforced NULL, `database/ddl/02_organization/
04_organization_address_restriction_trigger.sql` v1.1), but **can** now carry `country_pk`/
`state_pk`/`district_pk` (their administrative jurisdiction) — the original 2026-09-26 rule had
conflated "no premises" with "no recordable jurisdiction at all," which was too broad.
`api/routers/admin.py::create_organization()` now requires country/state/district for these 3
types; `update_organization()` allows setting them. Full rule:
`docs/03_Solution/modules/organization/04_organization_business_rules.md` §30 (v1.9.0).
Verified via 72 pytest integration tests (`tests/api/test_organization.py`, 8 classes, incl. a newer
`TestChildrenStats`) plus a
dedicated security audit (`docs/03_Solution/security/TIER2_SECURITY_AUDIT.md` — moved from
`code_explanations/` to a dedicated `security/` folder as part of the Tier 4 work).
Consumed at the time by `frontend/organization.html`'s 3-tab UI; since that page was deleted,
consumed by `frontend/admin.html`'s Organizations and Organization Hierarchy tabs (see
`frontend/` detail above). Merged to
`main` and released as v0.8.0 (see "Current position" above) — the 7th endpoint,
`/children-stats`, was added later, on top of Tier 4, and shipped as part of the v0.10.0
Family + Membership release, so it is now committed and released too.

**Two freezes live outside this module's own doc set, not inside it:** (1) the business rules
doc's freeze of exactly **8 organization types** — `KENDRA`, `NILACHALA_KUTIRA`,
`SMRUTI_MANDIRA` (unique, fixed business code) plus `ANCHALIKA`, `ZILLA`, `SAKHA`,
`SAKHA_ASANA`, `PATHA_CHAKRA` (multiple, sequence-generated — `ANC`/`ZL`/`SKH`/`SA`/`PC`) — a
type *inventory* freeze, distinct from the still-open type-to-type parent matrix above. **As
seeded, this is now 10 types, not 8**: `database/seed/01_foundation/02_master_data.sql`'s
`ORGANIZATION_TYPE` category adds `PARIBARIK_ASANA`/`PARIBARIK_SANGHA` (with matching new
`PARIBARIK_ASANA`/`PARIBARIK_SANGHA` sequences in `id_sequence_master`), neither of which is
part of the frozen 8-type inventory — a further divergence not yet reconciled (see Gotchas); (2)
`ORG-PENDING-001`, an `organization_short_code` column (`VARCHAR(5)`, `UNIQUE`, `NOT NULL`)
frozen in `docs/03_Solution/architecture/CROSS_MODULE_PRINCIPLES.md` §20.1. **As implemented,
this column does not match that spec**: `database/ddl/02_organization/03_organization.sql`
defines it as `organization_code`, `VARCHAR(10)`, `UNIQUE`, **nullable** (comment: "3-5 chars,
unique") — different name, wider column, and nullable rather than required. Separately, the
seeded `ORGANIZATION_TYPE` `master_data` rows (`database/seed/01_foundation/02_master_data.sql`
— formerly `database/seed/02_organization/01_organization_type_master.sql`, retired by this
migration) use `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA` as
business codes, not the short forms (`ANCHALIKA`/`ZILLA`/`SAKHA`) this module's own
business-rules doc uses (`SAKHA_ASANA`/`PATHA_CHAKRA` do match). See Gotchas and Open questions
for both — neither discrepancy blocks the read-only API above, which simply exposes whatever the
DDL/master_data actually define.

### 5. Person — demographics, addresses, trigram search (DB + API implemented, Tier 3, released v0.9.0)
`docs/03_Solution/modules/person/01_person_module_overview.md` through
`05_person_table_design.md` specify the Person module design. **As implemented**,
`database/ddl/03_person/02_person.sql` defines `nss.person` (28 columns) and
`03_person_address.sql` defines `nss.person_address` — following the same Foundation
`master_data` pattern established by the Organization migration: gender, marital_status, and
blood_group all resolve through `nss.master_data` (categories `GENDER`, `MARITAL_STATUS`,
`BLOOD_GROUP`) rather than dedicated per-domain master tables, and `person_address.address_type`
resolves through `master_data` category `ADDRESS_TYPE`. Only `01_person_master_tables.sql` (the
original per-domain gender/marital_status/address_type master tables) is superseded — its seed
data now lives in Foundation's `master_data` seed (see `database/README.md`). `person` includes
DB-level format validation CHECK constraints from day one (mobile, email, country phone code,
Aadhaar last-4, emergency phone) even though Tier 3 has no write endpoints yet — these are
schema-level safety nets, not currently reachable via the read-only API.

**API implemented.** `api/routers/person.py` (originally 304 lines / 4 endpoints; now 443 lines / 5, adding `/search-selectable`; prefix `/api/v1/person`) exposes
read-only GET endpoints — the same raw-`psycopg2`/`Depends(get_connection)` pattern as the
other tiers, and the first router to consume the newly-extracted `api/helpers.py` shared
`rows_to_models`/`row_to_model`/pagination-constant functions (Organization's router was
refactored to use the same helpers in the same change). Grouped by theme:
- **Core:** `/persons` (optional `gender_code`/`marital_status_code`/`blood_group_code`
  filters, `limit`/`offset` pagination) returns the compact `PersonSummaryResponse` shape (no
  Aadhaar/emergency/photo fields); `/persons/{person_pk}` returns the full `PersonResponse`
  shape (404 if missing). Both share `_PERSON_SUMMARY_SELECT`/`_PERSON_DETAIL_SELECT`, which
  LEFT JOIN `nss.master_data` three/four times respectively to resolve gender, marital status,
  blood group, and (detail only) emergency-contact relationship names.
- **Addresses:** `/persons/{person_pk}/addresses` (404 if the person itself doesn't exist, then
  all active addresses) — `_ADDRESS_SELECT` resolves address type via `master_data` and location
  through the `city_village_postal_code_map` junction into `city_village`/`postal_code`/
  `district`/`state`/`country`.
- **Search:** `/search?q=` — PostgreSQL trigram similarity via `similarity(p.first_name, %s) >
  0.45` / `similarity(p.last_name, %s) > 0.45` (an explicit-function-with-threshold call, not
  the `%` operator, matching Membership's identical pattern — see Key Workflow #6), combined
  with `ILIKE` prefix matching on `person_id`/`mobile_number`/`email` (email added alongside
  Tier 4). Email-shaped queries (containing `.` or `@`) are split on the first delimiter
  (`re.split(r'[.@]', q)[0]`) before the trigram comparison, so `"ramesh.mishra"` matches on
  `"ramesh"` rather than failing to match the literal dotted string — the same email-split rule
  Membership's search uses. Ordered by `similarity(p.first_name, %s) DESC`, capped at 50
  results.

**Security (PER-BR-081):** `aadhaar_encrypted` (BYTEA) and `aadhaar_hash` (VARCHAR) are never
returned by any endpoint or exposed in any Pydantic model — only `aadhaar_last4` is returned for
masked display. `api/schemas/person.py` (159 lines today) defines `PersonResponse` (full detail),
`PersonSummaryResponse` (list/search — omits Aadhaar, emergency contact, photo), and
`PersonAddressResponse`, all plain Pydantic models excluding audit columns, matching the
convention established in Tier 0.

A matching Person Verification UI (`frontend/person.html` + `frontend/assets/js/person.js`,
`personApp()` — both since deleted; this UI now lives in `admin.html`'s Person Directory tab)
and 61 pytest integration tests (`tests/api/test_person.py`, 6 classes) exist, plus a
dedicated security audit (`docs/03_Solution/security/TIER3_SECURITY_AUDIT.md` — moved from
`code_explanations/` to a dedicated `docs/03_Solution/security/` folder as part of the Tier 4
work, see Key Workflow #6). This
work was merged to `main` and tagged **v0.9.0**, alongside the Organization master-data
migration. See "Current position"
above and `docs/03_Solution/api/PERSON_API_CONTRACT.md` for the formal contract.

### 6. Family + Membership — the largest vertical slice yet (DB + API implemented, Tier 4, released v0.10.0)
`docs/03_Solution/modules/family/` and `docs/03_Solution/modules/membership/` specify the
design (both still `Version: 1.0, Status: DRAFT` — not yet reconciled to FROZEN even though the
implemented DDL already matches their table/column shapes 1:1, unlike Person's docs which were
reconciled to FROZEN v2.0.0 before its DDL landed). **As implemented:**

**Family** (`database/ddl/04_family/`, 5 tables): `family_group` (the family unit itself),
`family_relationship` (per-member relationship to the family, e.g. `FATHER`/`MOTHER`/`SON`),
`family_head_history` (who has headed the family and when — partial-unique-indexed so only one
row per family can be current), `family_transition_history` (family-level lifecycle
transitions), and `family_link` (added after the initial Tier 4 landing — see "Family Graph"
below). `api/routers/family.py` (prefix `/api/v1/family`) exposes 7 read-only
GET endpoints as of the v0.10.0 Tier 4 release: the original 4 — `/families` (list, filters, pagination), `/families/{family_pk}` (detail),
family members (relationships per family), and family head history (per family) — plus 3 newer
ones described below. **Added in Tier 5:** 9 more authenticated write endpoints (create family, add/remove family
member, create family link, list/add/revoke family admins, transfer family head — see Key
Workflow #9) were added directly to this same router file, bringing it to 16 endpoints total and
6 tables (`family_admin` added); its module docstring has already been updated to say "Tier 4
read-only + Tier 5 write endpoints" rather than the old stale "4 endpoints across 3 Family
tables" claim. 16 Pydantic
models in `api/schemas/family.py` as of the Tier 5 (up from the original 8: `FamilyGroupResponse`, `FamilyMemberResponse`
— gained an `is_head` field —,
`FamilyHeadHistoryResponse`, the 5 read-only additions below, plus 8 new write-request/response schemas for the Tier 5 endpoints above). A matching Family Verification UI
(`frontend/family.html` +
`frontend/assets/js/family.js`, `familyApp()` — both since deleted; this UI now lives in
`dashboard.html`'s Family tab) and 67 pytest integration tests
(`tests/api/test_family.py`, 8 classes) exist as of v0.10.0 — no test coverage yet for the 9 new
Tier 5 write endpoints.

**Family Graph — dynamic relationship computation (added after the initial Tier 4 landing).**
`database/ddl/04_family/05_family_link.sql` defines `nss.family_link`: a deliberately minimal
edge table storing only direct `PARENT_OF` (directed) and `SPOUSE_OF` (bidirectional, stored
once) relationships between two persons. Per its own header comment
(`Authority: ERP-DECISION — Graph-based dynamic relationship model`), every other kinship term
(grandfather, aunt, sister-in-law, ...) is computed on demand rather than stored — "when the
Family Head changes, zero data re-entry is required — the graph is the same, only the viewer
changes." The computation itself lives in a brand-new architectural layer, `api/services/`
(previously the codebase had only `routers`/`schemas`): `api/services/family_graph.py` builds an
in-memory graph from `family_link` rows (`build_family_graph()`) and computes relationship
labels relative to any viewer via BFS over `UP`/`DOWN`/`SPOUSE` steps
(`compute_relationships()`), using a `PATH_LABELS` table keyed by step-tuples with gendered
(male_label, female_label) pairs — e.g. `(UP, UP)` → ("Grandfather", "Grandmother"). Exposed via
`GET /families/{family_pk}/graph?viewer_person_pk=`, returning `list[FamilyGraphMemberResponse]`
(person fields plus `relationship_label`, `generation`, `is_head`, `spouse_person_pk`,
`parent_person_pks`). **`family_link` does not supersede `family_relationship`** — both tables
coexist for different purposes: `family_relationship` still backs `/members`, `/sakha-alignment`,
and head-history joins; `family_link` is read only by `/graph`. **No test coverage exists yet**
for this endpoint. The frontend (then `frontend/family.html`/`family.js`, now `dashboard.html`'s
Family tab) grew substantially (from a
simple list/filter/detail page to a 3-panel layout) to add a recursive tree renderer
(`buildTree()`/`renderTree()`/`_renderSubtree()`/`_renderCouple()`/`_renderPerson()`) and a
"View as" viewer selector (`changeViewer()`) that re-fetches `/graph` from a different person's
perspective.

**Sakha Alignment — FAM-036 majority rule (also added after the initial landing).**
`GET /families/{family_pk}/sakha-alignment` computes a family's *effective* Sakha as whichever
Sakha the majority of its members are actively affiliated with (falling back to the family's
stored `sakha_organization_pk` if no member has an affiliation), returning
`FamilySakhaAlignmentResponse` with per-member `is_home_sakha` mismatch flags. `is_aligned` is
hardcoded `True` by design — the `assigned_sakha_*` fields returned *are* the computed majority,
so alignment is tautological at the family level; individual mismatches still show up via
`is_home_sakha`. The same underlying SQL (a `family_majority` CTE ranking each family's Sakha
affiliations by `COUNT(*)` via `ROW_NUMBER() OVER (PARTITION BY family_group_pk ORDER BY
COUNT(*) DESC)`) is **also used by `_FAMILY_SELECT`** (so even the plain `/families` list now
reports the computed majority Sakha, not just the stored one) **and is now shared, not
duplicated,** with
`api/routers/organization.py`'s `/organizations/{pk}/children-stats` endpoint via a single
`FAMILY_MAJORITY_CTE_SQL` constant in `api/helpers.py` (see Key
Workflow #4 and Gotchas for the earlier duplication this replaced).

**Membership** (`database/ddl/05_membership/`, 14 tables — the largest module in the codebase):
`sangha_sevi` (the core membership record, one per person, carrying the permanent NSS-wide
Sangha Sevi ID) plus 13 supporting tables split into "current state" + "history" pairs:
`membership_status_history`, `membership_renewal_request`/`membership_renewal_history`,
`membership_transfer_history`, `membership_sakha_affiliation` (current Sakha assignment — a
partial unique index enforces at most one active affiliation per person **per organization**,
narrowed from "per person" (Tier 5) specifically so a member's home affiliation and a
cross-Sakha Darshak-attendance affiliation at a different Sakha can coexist as two active rows),
`probationary_member_review`,
`membership_journey_event` (a timeline of everything that's happened to a membership),
`parichaya_patra`/`parichaya_patra_history`, `anumati_patra`/`anumati_patra_history`
(the two membership credential/card documents), `darshak_attendance_registration` (new in Tier 5 — a member's registration to attend Sangha Puja as a Darshak at a different Sakha
than their own, SOL-MEM-006, 3-step approval chain), and `credential_sequence_counter` (new in Tier 5 — backs `api/helpers.py::next_credential_document_number()`, a per-(credential-type,
org, financial-year) counter distinct from the flat, never-reset `id_sequence_master`).
`api/routers/membership.py` exposes 8 endpoints: `/members` (list, filters,
pagination) and `/search` are gated by `require_permission("MEMBERSHIP_VIEW")`;
`/members/{member_pk}` (detail), Sakha affiliation history,
Parichaya Patra records, Anumati Patra records, and a journey-event timeline (the last four
per-member sub-resources scoped by `member_pk`) instead use an **ownership model** (v0.11.0)`/`require_self_or_permission()` helper) —
`get_current_user` plus either `MEMBERSHIP_VIEW` or being the member themself; and an 8th
endpoint, `/organizations/{organization_pk}/darshak-summary` (v0.11.0), returns per-org Darshak counts for the new Org Dashboard. 5 Pydantic
models in `api/schemas/membership.py`: `MemberResponse`, `SakhaAffiliationResponse`,
`ParichayaPatraResponse`,
`AnumatiPatraResponse`, `JourneyEventResponse` (plus the newer `OrgDarshakSummaryResponse`).

**Membership status vocabulary — extends the unified `STATUS` category, doesn't fork it.**
Rather than adding a dedicated `MEMBERSHIP_STATUS` category, Tier 4 added 3 new values directly
to Foundation's shared `STATUS` category (`RENEWAL_PENDING`, `ON_HOLD`, `DISCIPLINARY_REVIEW`),
bringing it to 16 values total (13→16), and gave `nss.master_data` a new
`applicable_modules TEXT[]` column so each module's API can filter to its own relevant subset
(`'<MODULE>' = ANY(applicable_modules)`, with `NULL` meaning "applies everywhere"). Every one of
the 16 values is tagged with which module(s) it applies to: `ORGANIZATION` (7: `PROPOSED`,
`APPROVED`, `ACTIVE`, `INACTIVE`, `SUSPENDED`, `DISSOLVED`, `ARCHIVED`), `MEMBERSHIP` (12:
`ACTIVE`, `INACTIVE`, `SUSPENDED`, `LAPSED`, `TRANSFERRED`, `RESIGNED`, `EXPELLED`, `ARCHIVED`,
`EXPIRED`, `RENEWAL_PENDING`, `ON_HOLD`, `DISCIPLINARY_REVIEW`), and `PERSON` (4: `ACTIVE`,
`INACTIVE`, `DECEASED`, `ARCHIVED`). `DECEASED` is `{PERSON}`-only (a membership record itself
can't be deceased — the person behind it can); `EXPIRED` is tagged `{MEMBERSHIP}` (not a
separate "Credential" scope — an earlier seed revision tagged it `{CREDENTIAL}` instead, which
undersold the real relationship: a membership going stale because its holder never renewed
their Parichaya Patra/Anumati Patra is exactly how expiry actually happens in practice, and
`{MEMBERSHIP}` is the correct tag). `parichaya_patra_history`/`anumati_patra_history` both
record a `change_type`/`new_status` of `EXPIRED` alongside `ISSUED`/`RENEWED`/`CANCELLED`/
`REPLACED`. One architectural nuance remains: `parichaya_patra.status`/`anumati_patra.status`
are each a plain `VARCHAR(20)` with their own inline `CHECK` constraint (`chk_pp_status`, values
`ACTIVE`/`EXPIRED`/`CANCELLED`/`REPLACED`) — they are **not** FKs into `nss.master_data`, so the
`master_data` `STATUS.EXPIRED` row isn't what these tables actually store; it's a parallel
reference/lookup entry (e.g. for a UI dropdown) rather than the credential tables' backing
value. That's also why `EXPIRED` never appears in `membership_status_history` — a lapsed
credential doesn't automatically flip `sangha_sevi`'s own status; that's a business-rule/
application-layer decision, not something enforced by a DB constraint today. `ACTIVE`/
`INACTIVE`/`ARCHIVED` are the only 3
`master_data` `STATUS` values shared across all of
Organization/Membership/Person.

**Unified `STATUS` category — full table, by applicable module** (`display_order` order,
`✓` = tagged in `applicable_modules`; despite the name, `EXPIRED`'s actual storage for
Parichaya/Anumati Patra documents is each table's own `CHECK`-constrained column, not read
through this table — see note above):

| # | `value_code` | Name | Org | Membership | Person | Description |
|--:|---|---|:-:|:-:|:-:|---|
| 1 | `PROPOSED` | Proposed | ✓ | | | Entity proposed but not yet approved |
| 2 | `APPROVED` | Approved | ✓ | | | Approved by governance, pending activation |
| 3 | `ACTIVE` | Active | ✓ | ✓ | ✓ | Currently operational / active |
| 4 | `INACTIVE` | Inactive | ✓ | ✓ | ✓ | Temporarily non-operational |
| 5 | `SUSPENDED` | Suspended | ✓ | ✓ | | Suspended by governance decision |
| 6 | `LAPSED` | Lapsed | | ✓ | | Lapsed due to non-renewal or non-attendance (Bye-Law §D(d)) |
| 7 | `TRANSFERRED` | Transferred | | ✓ | | Transferred to another unit |
| 8 | `RESIGNED` | Resigned | | ✓ | | Voluntarily departed |
| 9 | `EXPELLED` | Expelled | | ✓ | | Expelled by governance decision (Bye-Law §D(d)(iii)) |
| 10 | `DECEASED` | Deceased | | | ✓ | Person is deceased (Bye-Law §D(d)(i)) |
| 11 | `DISSOLVED` | Dissolved | ✓ | | | Organization permanently dissolved (Bye-Law §I) |
| 12 | `ARCHIVED` | Archived | ✓ | ✓ | ✓ | Permanently closed, retained for history |
| 13 | `EXPIRED` | Expired | | ✓ | | Membership/document term has expired (Bye-Law §C(1)(c)) — set when a Parichaya Patra/Anumati Patra lapses from non-renewal |
| 14 | `RENEWAL_PENDING` | Renewal Pending | | ✓ | | Membership renewal requested, awaiting approval |
| 15 | `ON_HOLD` | On Hold | | ✓ | | Membership temporarily on hold (administrative) |
| 16 | `DISCIPLINARY_REVIEW` | Disciplinary Review | | ✓ | | Under disciplinary review by governance (Bye-Law §D(d)(iii)) |
| | **Total per module** | | **7** | **12** | **4** | |

**This changed Organization's existing `/statuses` endpoint's
behavior**:
`api/routers/organization.py`'s `list_statuses()` now adds
`AND ('ORGANIZATION' = ANY(md.applicable_modules) OR md.applicable_modules IS NULL)` to its
query, so it returns 7 statuses, not all 16 (or the pre-Tier-4 13) — see the Gotcha and Open
Question on the resulting stale test below.

**Three-tier member identity model** (the module's central, non-obvious concept): (1) **Sangha
Sevi ID** (e.g. `SS1`) — permanent, NSS-wide, assigned once on `sangha_sevi`; (2) **Local Sakha
Number / ERP Number** (e.g. `ESS1192`) — Sakha-scoped, auto-generated, lives on
`membership_sakha_affiliation`, archived (never reassigned) on transfer and reactivated if the
person returns; (3) **Kendra Number** (e.g. `345/2026/2027`) — annual, resets each financial
year, lives on `parichaya_patra.document_number`. `/search`'s member search checks all three
plus name (trigram, threshold 0.45) and mobile/email — 7 fields total; a separate 4-field
person search (person_id, name trigram, mobile, email) supports the case where no membership
record exists yet. Both trigram paths split email-shaped queries on `.`/`@`
(`re.split(r'[.@]', q)[0]`) before computing similarity, to avoid a long literal string
producing spurious matches; both auto-select when exactly one result comes back, and both use
the inline-detail-panel pattern `personApp()` established (no tab switch on selection). A
matching Membership Verification UI (`frontend/membership.html` — 747 lines, at the time the
largest
frontend page in the repo — + `frontend/assets/js/membership.js`, `membershipApp()`; both since
deleted, this UI now lives in `dashboard.html`'s Membership tab and `admin.html`'s Member
Directory tab) and 99
pytest integration tests (`tests/api/test_membership.py`, the largest test file in the repo) exist.

**Documentation infrastructure changes landed alongside Tier 4:** a new consolidated
`docs/03_Solution/api/API_CONTRACT.md` (all tiers, common conventions) sits
alongside the existing per-tier contract docs — Family and Membership have **no** dedicated
`FAMILY_API_CONTRACT.md`/`MEMBERSHIP_API_CONTRACT.md`; `API_CONTRACT.md` is their only formal
contract, a pattern shift from Tiers 0-3's one-file-per-tier convention. Security audit reports
moved from `docs/03_Solution/code_explanations/TIERn_SECURITY_AUDIT.md` to a dedicated
`docs/03_Solution/security/` folder (now `TIER0_SECURITY_AUDIT.md` through
`TIER4_SECURITY_AUDIT.md` plus a consolidated `SECURITY_AUDIT_TIER0_4.md`). A new
`docs/03_Solution/architecture/GETTING_STARTED.md` setup guide was also added, overlapping with
(and currently the most current of) `README.md`'s Getting Started section and this file's Setup
& running section.

**Status:** implemented, tested, merged to `main`, and released as **v0.10.0**, followed by
three hotfix tags — **v0.10.1** (`6b31500` — wired `family_link` into the build scripts,
extended `render_build.sh` through Tier 4), **v0.10.2** (`621ea52` — Neon role-creation-order
fix, creates `nss_db_owner`/`nss_db_backend` before granting), and **v0.10.3** (`6677b95` —
idempotent DDL `CREATE TABLE`/`INDEX` plus idempotent seed `INSERT`s, root-causing a Neon
schema/data drift bug), then a performance-hardening release, **v0.10.4** (composite partial
indexes, connection-pool sizing, `--workers 2`, non-blocking frontend fetches). See "Current
position"
above,
Conventions & Gotchas for the ID-format decision this branch also introduced, and Open
questions / TODOs for the still-real follow-up items it left behind (`03_validate.sh`
staleness, the duplicated FAM-036 CTE, missing `/graph` and
`/membership-summary` test coverage, stale router docstrings — `.ps1` build-script parity was
fixed in v0.10.4). The performance-hardening pass on top of this release, **v0.10.4**, is
covered above — see Gotchas.

### 7. Foundation API — master data, geography, config, runtime (implemented, Tier 1)
`api/routers/foundation.py` (~1740 lines today, 33 endpoints; prefix `/api/v1/foundation`) originally exposed 17 read-only GET
endpoints across 11 of the 12 Foundation tables — the same raw-`psycopg2`/`Depends(get_connection)`
pattern as Tier 0, plus new Tier-1 conventions (query-param filtering instead of nested paths,
e.g. `?category_code=`/`?country_pk=`; hierarchical drill-down Country→State→District→
City/Village; no pagination). Grouped by theme:
- **Master data:** `/categories`, `/categories/{pk}`, `/master-data` (optional `category_code`/
  `category_pk` filter), `/master-data/{pk}` — `nss.master_category`/`nss.master_data`.
- **System config:** `/settings`, `/settings/{setting_key}` (business-key lookup, not PK),
  `/sequences` (excludes `current_value` — no detail-by-pk endpoint) — `nss.system_setting`/
  `nss.id_sequence_master`.
- **Geographic:** `/countries`, `/states` (optional `country_pk`), `/districts` (optional
  `state_pk`), `/cities` (optional `district_pk`, currently empty — no seed data),
  `/postal-codes` (optional `state_pk` or `country_pk`), `/postal-code-mappings` (pure M:N
  junction, no `is_active`, currently empty) — plus each entity's `/{pk}` detail route.
- **Runtime:** `/documents` (optional `document_type_code`, currently empty — no seed data;
  excludes the unimplemented `person_pk`/`uploaded_by_sangha_sevi_pk` FKs).

`nss.field_change_log` is the one Foundation table **deliberately not exposed** — deferred to
Tier 5 once auth exists (`tests/api/test_foundation.py::TestChangeLogNotExposed` guards this by
asserting `/api/v1/foundation/change-log` 404s/405s; the Tier 5 viewer is `GET /api/v1/audit/change-log`
in `api/routers/audit.py`, gated by `AUDIT_VIEW`). All list endpoints filter
`WHERE is_active = TRUE` (except the junction table, which has no such column); all detail
endpoints 404 on missing/inactive rows; malformed UUIDs 422 via Pydantic/FastAPI path-param
validation. Full contract, example responses, and the 11 response-schema fields (incl. every
deliberately-excluded column) are in
`docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`; a line-by-line implementation
walkthrough is in `docs/03_Solution/code_explanations/API_CODE_EXPLANATIONS.md`.
Verified via 59 pytest integration tests (`tests/api/test_foundation.py`, 13 classes) plus a
dedicated security audit (`docs/03_Solution/security/TIER1_SECURITY_AUDIT.md`) with no blocking
findings. Consumed at the time by `frontend/foundation.html`'s 4-tab UI; since that page was
deleted, consumed by `frontend/admin.html`'s Reference Data and Geography tabs (see `frontend/`
detail above).

### 8. Security middleware — headers, CORS, rate limiting (cross-tier, implemented)
Applies to every route across all four routers plus the static frontend — see the Architecture
diagram above for exact registration order (`SlowAPIMiddleware` → `CORSMiddleware` if configured
→ `add_security_headers`). Three independent, individually-toggleable concerns:
- **Security headers** (`api/middleware.py`) — always on, no config: 4 headers on every
  response, plus `Cache-Control: no-store` scoped to `/api/*` only (so `/`, `/foundation`,
  `/organization`, `/person`, and `/assets/*` remain normally cacheable).
- **CORS** — off by default (`CORS_ORIGINS` empty); when set, `CORSMiddleware` allows only the
  listed origins, `GET` only, credentials allowed, never a wildcard origin.
- **Rate limiting** — on by default (`RATE_LIMIT="60/minute"`), keyed per client IP
  (`get_remote_address`), enforced globally (no route currently opts in to a different limit).
`tests/security/test_security_headers.py` verifies all three — including a real bug it
caught during development: an earlier version of the middleware configured the `Limiter` but
never registered `SlowAPIMiddleware`, so the limit was defined but never enforced.
`tests/api/test_organization.py::TestOrganizationSecurity` and
`tests/api/test_person.py::TestPersonSecurity` separately re-verify the
same headers/`Cache-Control` behavior against the Organization and Person routers and UIs. Full
walkthrough: `docs/03_Solution/code_explanations/SECURITY_CODE_EXPLANATIONS.md`;
test walkthrough: `TESTING_CODE_EXPLANATIONS.md` (same folder); audit
verdicts: `docs/03_Solution/security/TIER0_SECURITY_AUDIT.md` through
`TIER4_SECURITY_AUDIT.md`, plus a consolidated `SECURITY_AUDIT_TIER0_4.md` — moved out of
`code_explanations/` into a dedicated `security/` folder as part of the Tier 4 work.

### 9. Tier 5 (Authentication + Administration) — self-registration → approval → login → RBAC (v0.11.0)

**Not yet merged/released — see the Tier 5 subsection under Architecture above.** This is the
first genuinely write-path, authenticated vertical slice in the codebase. Two independent
entry points converge on the same `sangha_sevi`/`membership_sakha_affiliation` state:

**Self-registration flow** (`POST /api/v1/register`, `api/routers/registration.py`):
0. Before submitting, `register.html`/`register.js` populates its dropdowns from 4 new, public,
   unauthenticated endpoints (Tier 5): `GET /api/v1/register/reference-data` (countries +
   gender/marital-status/blood-group/membership-type master-data + the Sakha list, bundled into
   one call) and `GET /states`/`/districts`/`/postal-codes` for the location cascade — each a
   thin wrapper over `foundation.py`'s/`organization.py`'s own shared query functions
   (`fetch_countries()` etc.). This fixed a real regression: Tier 5's blanket
   `FOUNDATION_VIEW`/`ORGANIZATION_VIEW` gating on the authenticated Foundation/Organization
   endpoints had silently emptied every dropdown on this page, since a prospective member has no
   JWT yet.
1. A prospective member submits demographics + optional membership claim (Sakha, membership
   type, claimed Local Sakha Number) + a password.
2. The endpoint creates `nss.person` (via `next_id(cur, "PERSON")`) and — only when
   `has_membership` is true — `nss.user_account(account_status='PENDING_APPROVAL')` in one
   transaction (no membership claim means no account, since an account with no path to a
   `sangha_sevi` can never log in; the typed password is discarded). **No
   `sangha_sevi`/`membership_sakha_affiliation` row exists yet**, deliberately: those are only
   created on admin approval, so a rejected/abandoned registration never leaves a dangling
   membership identity.
3. When membership details were supplied, a `nss.registration_claim(claim_status='PENDING')` row
   captures the claim for later review (a partial unique index enforces at most one `PENDING`
   claim per `user_account`). A person who registered without membership later submits the same
   account + claim via public `POST /register/lookup-existing` (person_id + DOB check; 404 on
   mismatch, 409 if they already have an account, pending claim or active `sangha_sevi`) then
   `POST /register/claim` (`register.js` `mode = "existing"`).
4. `PENDING_APPROVAL` accounts cannot log in (`POST /api/v1/auth/login` checks
   `account_status` and 403s with an explanatory message before even checking the password).

**Admin approval flow** (`api/routers/claim_approval.py`, scoped to the reviewing admin's
`admin_scope` organizations unless they hold an `NSS-WIDE` scope):
1. `GET /api/v1/admin/claims?claim_status=PENDING` lists claims for the admin's orgs;
   `PATCH /{pk}` lets the admin correct claim/person fields before deciding.
2. `POST /{pk}/approve` — branches on whether the claimed membership type is `PROBATIONARY`
   ("Darshaka"): Darshaka claims always get a **new** `sangha_sevi_id` (`next_id(cur,
   "SANGHA_SEVI")`); non-Darshaka claims must supply a `claimed_local_sakha_number` that either
   matches an *existing* `sangha_sevi_id` (same person only — a mismatch 409s, telling the admin
   to reject instead) or becomes the new record's ID directly. Either path then creates a
   `membership_sakha_affiliation` row and flips `user_account.account_status` to `ACTIVE`.
3. `POST /{pk}/reject` leaves the account `PENDING_APPROVAL` (the person can be re-reviewed
   later, e.g. after correcting their claim) and requires a remarks string.
4. `PATCH /api/v1/admin/users/{pk}/status` (`api/routers/admin.py::update_status`) no longer
   provisions a `sangha_sevi` (it used to, diverging from `approve_claim()`). Activating a
   `PENDING_APPROVAL` account is refused with 422 when a PENDING claim exists (approve it in
   Registration Approvals instead) or when the person has no active `sangha_sevi` (create one
   first via `POST /admin/sangha-sevi`). `GET /admin/users` (`list_users`) only returns accounts
   tied to an active `sangha_sevi` (`ss.sangha_sevi_pk IS NOT NULL`) — uncommitted working-tree
   changes. `sangha_sevi` rows are still inserted in three independent places:
   `claim_approval.py::approve_claim()`, `admin.py::create_user()` and `create_sangha_sevi()`.

**Login + RBAC flow** (`POST /api/v1/auth/login`, then every protected endpoint):
1. `login_id` is resolved to a `person_pk` by trying `sangha_sevi_id` first (case-insensitive),
   falling back to `person_id` — so a person with no `sangha_sevi` yet (e.g. mid-approval) can
   still log in with their Person ID once `ACTIVE`.
2. Password verified with Argon2 (`argon2-cffi`); 5 consecutive failures set `locked_until` 30
   seconds in the future (`is_account_locked()`/`calculate_lockout_until()` in
   `auth_service.py`) — the lockout self-clears, there's no manual unlock endpoint.
3. On success, a JWT access token (30 min) + refresh token (7 days) are issued, both carrying a
   `session_start` claim from the *original* login — `decode_token()` rejects any token (access
   or refreshed) once 30 days have passed since that original `session_start`, regardless of how
   many times the access token has been refreshed in between (the "absolute session max").
4. Every protected endpoint depends on `require_permission(code)`/`require_any_permission(...)`
   (`api/dependencies/rbac.py`), which wraps `get_current_user()` (`api/dependencies/auth.py`,
   decodes the Bearer JWT) and then `rbac_service.load_user_context()` — a fresh DB load per
   request (no caching) of the union of every active role's permissions
   (`user_role` → `role_permission` → `permission_master`) plus one `ScopeInfo` per active role
   assignment (`user_role` → `admin_scope`). **`permission_master`/`role_permission` are now
   seeded** (`database/seed/00_bootstrap/01_permission_master.sql`/`03_role_permission.sql`) — `FOUNDATION_VIEW`/`ORGANIZATION_VIEW`/`PERSON_VIEW`/`PERSON_VIEW_SENSITIVE`/
   `FAMILY_VIEW`/`MEMBERSHIP_VIEW`/`AUDIT_VIEW` plus the admin/user-management permission set are
   mapped to roles, so `require_permission()` calls no longer blanket-403 for every role — this
   supersedes the "no seed data change... every endpoint 403s for everyone" state described
   earlier in this branch's history.
5. `PATCH /api/v1/admin/organizations/{pk}` (and its sibling `PATCH .../short-code`, whose gate
   was fixed to match) depend on `require_any_permission("ORGANIZATION_MANAGE",
   "ORGANIZATION_VIEW")` as usual, then **additionally** run a manual, subtree-aware scope check
   in the router body (`_require_org_in_scope`, ADMIN-BR-076/077): `NSS_ERP_ADMIN`/NSS-WIDE edits
   any org; any other scoped admin edits only organizations inside their own scope subtree (their
   org + descendants) — permission alone never confers global reach. `POST
   /api/v1/admin/organizations` (create) remains `NSS_ERP_ADMIN`-only except for the two
   Sakha-admin-gated `KUMARI_SANGHA`/`SEVAK_SANGHA` types (ORG-BR-101/102). `PATCH
   /api/v1/admin/organizations/{pk}` also supports re-parenting via `parent_organization_pk`
   (validated against `_ALLOWED_PARENT_TYPES`) — backs the new "Assign Sakhas" admin
   tab (see `frontend/` detail above).

### 10. Member-assisted geographic entry — propose → review → approve/correct (Tier 5)

1. A logged-in member whose account has an active Sangha Sevi record proposes a value the lists
   lack via `POST /api/v1/foundation/{districts|postal-codes|post-offices|city-villages}/propose`
   (`api/routers/foundation.py`, gated by `get_current_user`; 403 without a Sangha Sevi). The row
   is inserted with `entry_status='PENDING'` and `submitted_by_sangha_sevi_pk` set; shared
   dropdowns only show `APPROVED` rows, and uniqueness only applies among APPROVED active rows
   (partial unique indexes, FND-BR-090). The registration flow likewise creates missing cities /
   post offices on submit (`resolve_or_create_post_office()`).
2. A `FOUNDATION_MANAGE` admin reviews the queue in `admin.html`'s **Geo Approvals** tab
   (`loadGeoEntries()`), backed by `api/routers/geo_approval.py`
   (`GET /api/v1/admin/geo-entries/{entity}` + detail), scope-filtered by the submitter's
   organization (ADMIN-BR-076).
3. `POST .../approve` flips PENDING to APPROVED (422 if not pending, 409 if an approved duplicate
   exists); `POST .../correct` find-or-creates the canonical row, marks the entry `CORRECTED`
   (`corrected_into_<entity>_pk`, CHECK-enforced) and re-points dependent `person_address` FKs.
4. The front-end component for picking-or-proposing is `frontend/assets/js/nss-combobox.js`
   (`nssCombobox()`); it is loaded by `register.html`/`dashboard.html`/`admin.html` but no page
   instantiates it yet. Tests: `tests/api/test_geo_approval.py`.

## Conventions & gotchas

- **`_pk` vs business identifier suffix — actual convention differs from some docs.** The SQL
  DDL consistently uses `<entity>_pk` (UUID) for internal surrogate keys and `<entity>_code`
  for short, often human-assigned reference codes (`organization_code`, `country_code`,
  `sequence_code`, `category_code`) — but every *system-generated, sequence-based* business
  identifier is named `<entity>_id`, not `<entity>_code`: `person.person_id`,
  `organization.organization_id`, `family_group.family_id`, `sangha_sevi.sangha_sevi_id`. This
  is a real, consistent pattern across Tiers 2-4, not a one-off exception — `CLAUDE.md`
  documents both suffixes. Some newer
  SOLUTION-layer module docs (e.g. `DATABASE_DESIGN_STANDARDS.md`)
  use `_id` in their own examples instead — that's a doc-side inconsistency, not a convention
  change; use `_id` for system-generated sequence identifiers and `_code` for short/reference
  codes in new DDL, matching the pattern above.
- **Family and Membership now have read-only APIs too, released as v0.10.0.**
  `api/routers/family.py`/`api/routers/membership.py` (Tier 4) read all 16 Family/Membership
  tables — the Tier 0 bootstrap-RBAC endpoints, the Tier 2
  Organization endpoints, the Tier 3 Person endpoints, and the Tier 4 Family/Membership
  endpoints (see Key
  Workflow #6) are the DB-backed data exposed today. All five tiers remain deliberately read-only;
  the earlier Django ORM track that once described a second, unreconciled version of these
  tables has been fully removed (see Architecture and Key Workflow #3/#4/#5/#6 above). All five
  tiers are now merged and released (v0.6.0-v0.10.0, with v0.10.1-v0.10.3 as follow-up hotfix
  tags and v0.10.4 as a performance-hardening release) — see "Current position" above.
- **`backend/` no longer exists on disk.** The Django prototype (`config`, `authentication`,
  `dashboard`, `foundation`, `family`, `membership`, `governance`, `attendance`, `heritage`
  apps, templates, static files, `manage.py`) was fully archived and removed once the FastAPI
  direction was adopted. Nothing in this repo references it anymore except historical git
  commits.
- **`api/` has security middleware; Tiers 1-4 gained permission-gating partway through this
  branch's development, Family later gained a full ownership-based auth model, and
  Tier 5 adds full auth+RBAC.** `api/main.py` includes `api/routers/bootstrap.py` (Tier 0),
  `api/routers/foundation.py` (Tier 1),
  `api/routers/organization.py` (Tier 2),
  `api/routers/person.py` (Tier 3), `api/routers/family.py`/`api/routers/membership.py` (Tier 4,
  released v0.10.0), plus (Tier 5) `api/routers/auth.py`, `admin.py`,
  `registration.py`, `claim_approval.py`, `audit.py` — 12 routers total, on top of
  the cross-tier security middleware stack (rate limiting, opt-in CORS, security headers, and
  now a Content-Security-Policy — see
  Architecture and Key Workflow #8 above). **`foundation.py`/`organization.py`/`person.py`/
  `membership.py` now depend on `require_permission("<MODULE>_VIEW")` on every GET endpoint** —
  this is new on this branch and not the Tier 0-4-released behavior. `family.py` took a
  different, later path: rather than a blanket `FAMILY_VIEW` gate, every one of its 16 endpoints
  (the 7 original reads and the 9 Tier 5 writes) now depends on `get_current_user` at minimum,
  with an **ownership model** layered on top — a person reaches their own family purely through
  their `family_relationship`/`family_admin` row, with `FAMILY_VIEW`/`FAMILY_MANAGE` as the
  admin override for browsing families the caller doesn't belong to (see
  `api/routers/family.py`'s module docstring and `_require_family_view`/`_require_family_manage`/
  `_require_family_head` helpers; covered by `tests/api/test_family_ownership.py`).
  **`bootstrap.py`'s 4 endpoints are now the only routes in the entire API left unauthenticated**
  — the deferred item this bullet used to flag ("wire `FAMILY_VIEW` into `family.py`'s GETs, or
  drop it") is resolved, just not the way it was originally framed. The
  Tier 5 routers add request-level identity (JWT) and
  permission checks the same way (`require_permission`/`require_any_permission`); **these no
  longer blanket-403**, since `permission_master`/`role_permission` are now seeded (see Setup
  above) — this corrects an earlier state of this same branch where they did.
- **Governance/standards docs are far ahead of the code.** `docs/00_Project_Governance/STD/`
  (naming conventions, audit standards, security standards, master data catalog) describes a
  mature target architecture (RBAC tables, RLS, full audit trail with `*_by_sangha_sevi_pk`
  columns, etc.) that the current `api/` code does not yet fully implement, though the Tier 5
  branch has closed much of that gap (RBAC enforcement, permission seeding, CSP) — Tier 0's
  own 4 endpoints remain zero-auth by design (verification-only). Treat the STD docs as the
  destination, not the current state.
- **Person module docs vs. Organization module docs.** Both are now implemented in SQL+API, and
  both diverge from their own frozen SOLUTION-layer design docs in ways that haven't been
  reconciled — don't confuse "documented" with "built as documented" for either. Person's design
  (`docs/03_Solution/modules/person/`, v1.0.0 SOURCE ALIGNED) is implemented as
  `database/ddl/03_person/02_person.sql` (`person`, 28 columns) and `03_person_address.sql`
  (`person_address`) — the `person_id`/`person_code` naming disagreement flagged in earlier
  passes of this doc is **now resolved**: the implemented DDL uses `person_id`, matching the
  design doc (see Key Workflow #3). What the design doc does *not* anticipate is the
  Foundation-`master_data` pattern: gender/marital_status/blood_group/address_type resolve
  through `nss.master_data` rather than the doc's own dedicated per-domain master tables — the
  same "Master Data Driven" migration already applied to Organization (see the
  `organization_type_master`/`organization_status_master` Gotcha below) was applied to Person's
  DDL from the start, so Person's frozen design docs and its implemented DDL diverge on table
  count/shape the same way Organization's do. Person's design used to describe a second table,
  `document_master`, but that was reassigned to Foundation (`DOC-ARCH-001` — see the Gotcha
  below). Organization's generic 3-table structure **is no longer** implemented in SQL — only the
  `organization` table remains, with type/status now sourced from Foundation's `master_data` (see
  the frozen-design-vs-implementation Gotcha below); separately, the implemented
  `organization_code` column doesn't match the frozen `ORG-PENDING-001` spec
  (`organization_short_code`, `VARCHAR(5)`, `NOT NULL` vs. the actual `VARCHAR(10)`, nullable
  `organization_code`), and the seeded organization-type codes don't match the design docs' short
  forms — see Key Workflow #4.
- **Tier numbering is now unified (former "Tier 3" collision resolved).**
  `IMPLEMENTATION_DEPENDENCY_ORDER.md` (`IMPLEMENTATION-TIER-001`) has been restructured to the
  single agreed build-order sequence (Tiers 0–13), so "Tier 2" means Organization and "Tier 3"
  means Person in every doc — `CLAUDE.md`, this document's own "Current position"/Key Workflow
  numbering, the `docs/03_Solution/code_explanations/` per-layer docs, and `docs/03_Solution/api/`
  contract docs. Previously the frozen dependency doc bundled Person + Organization at a single
  "Tier 2" and reserved "Tier 3" for Heritage, which collided with the implementation-sequence
  labels used everywhere else. Heritage is now Tier 7 by build order — its only hard dependency
  is Foundation + Person (not Membership; see HER-059), so its position reflects build order, not
  dependency depth. No open governance item remains here.
- **`organization_type_master`/`organization_status_master` retirement contradicts multiple
  frozen/governance-aligned documents — needs a human governance decision, not a doc edit here.**
  A migration removed the dedicated `organization_type_master`/`organization_status_master`
  tables and replaced them with rows in Foundation's generic `master_data` (categories
  `ORGANIZATION_TYPE`, 10 values; `STATUS`, a renamed/unified `MEMBERSHIP_STATUS`, now 13 values
  shared across modules) — matching the project's frozen "Master Data Driven" principle, but
  leaving several other frozen documents now factually wrong about the physical schema, and none
  of them has been reconciled:
  - `docs/03_Solution/architecture/FK_DEPENDENCY_GRAPH.md` (`SOL-ARCH-009`, FROZEN) still lists
    both tables as nodes in its 86-table physical FK dependency graph.
  - `docs/03_Solution/architecture/DDL_CREATION_ORDER.md` (`SOL-ARCH-010`, FROZEN) still lists
    both tables in its numbered `CREATE TABLE` sequence.
  - `docs/03_Solution/modules/organization/` design docs (v1.1.0, GOVERNANCE ALIGNED) still
    describe a 3-table Organization design (`organization_type_master`,
    `organization_status_master`, `organization`) as the frozen physical schema.
  - `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` (`SOL-DB-001`, DRAFT — already
    tracked elsewhere in this section as having other stale/contradicted claims) references both
    tables as worked examples.
  - `docs/00_Project_Governance/STD/02_naming_conventions.md` and
    `03_master_data_catalog.md` (Governance Baseline, FROZEN) both reference both tables by name.
  Per this project's own convention that the Governance Baseline is frozen and not to be
  redesigned without an explicit governance decision, none of the above have been edited to
  match the new implementation, and the new implementation hasn't been rolled back to match
  them either. This is flagged here only — a human governance decision is needed on whether the
  frozen 3-table design should be amended to match the `master_data` implementation, or the
  implementation should be reverted to the frozen 3-table design. See also Key Workflow #4 and
  Open questions / TODOs.
- **`.env` loading tolerates a Windows BOM.** `api/config.py` calls
  `load_dotenv(_env_path, encoding="utf-8-sig")` rather than plain UTF-8 — some Windows editors
  save `api/.env` with a UTF-8 BOM, which previously caused `DB_NAME` (the first key) to be
  silently misread and `Settings.validate()` to report it missing. Mirrors the earlier
  `requirements.txt` UTF-16LE fix noted in Setup & running above — a recurring Windows-encoding
  class of bug in this repo.
- **pytest is now configured — no longer "no tests."** `pytest.ini` (repo root) + `tests/`
  package, now four suites — see `tests/README.md` for counts and coverage, and the "Test layer"
  bullet under Key architectural facts per tier above. `test_kumari_transition_has_event`
  `pytest.skip()`s when its seed row is absent.
  `tests/conftest.py`'s `client` fixture wraps
  `fastapi.testclient.TestClient` against a **real** local Postgres DB — nothing is mocked, so
  a bootstrapped database + `api/.env` are prerequisites for running them. `pytest` and `httpx`
  (required by `TestClient` at import time) are pinned in `requirements.txt`. No lint/format
  tooling is configured yet.
- **Git remotes.** `git remote -v` shows two remotes: `personal`
  (`github.com/sandeeppanda22/NSS_ERP`, daily dev) and `org`
  (`github.com/NilachalaSaraswataSangha/NSS_ERP`, the production/deploy target).
  `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` §6 uses the `org` alias consistently
  in its Production remote and Flow rows.
- **Second "standards" location.** `docs/03_Solution/standards/lifecycle/` (`SOL-LIFE-001`/
  `PARTICIPATION_LIFECYCLE_RULES.md`, `SOL-LIFE-002`/`PERSON_LIFECYCLE_RULES.md`) is a distinct
  path from the pre-existing governance-layer `docs/00_Project_Governance/STD/` — both are
  legitimately different layers (SOLUTION vs. GOV per the lifecycle described in `CLAUDE.md`).
  It has its own `README.md` explaining the two documents and their relationship, but neither
  `STD/README.md` nor any top-level doc cross-references the other standards location, and the
  Sevak/Mahila/Kumari module business-rules docs don't yet cite `SOL-LIFE-001` even though its
  own text says they should reference it rather than duplicate its rules.
- **`docs/03_Solution/modules/foundation/` describes more tables than one might expect for
  "Foundation."** It covers 10 tables: the original 8 master data/geography/sequence tables
  plus `document_master` and `field_change_log`. The implemented `database/ddl/01_foundation/`
  has 12 tables, 2 more than this design doc describes (`postal_code`,
  `city_village_postal_code_map`) — implementation is ahead of the design doc for those two,
  see the Foundation Gotcha below.
- **`document_master` is Foundation-owned; RBAC table ownership is split between Authentication
  and Administration** (`CROSS_MODULE_PRINCIPLES.md`, `ARCH-CROSS-001`, FROZEN). `DOC-ARCH-001`
  establishes Foundation as the sole owner of a common `document_master` document registry
  (Person, Heritage, and Publications are consumers via FK, not owners) and a Foundation-owned
  `field_change_log` table for business-significant field-level change tracking, distinct from
  each module's own `_history` tables. Separately, a Table Ownership Declaration makes
  `user_account`/`password_history` exclusively Authentication-owned and the 5 RBAC tables
  (`role_master`, `permission_master`, `role_permission`, `user_role`, `admin_scope`)
  exclusively Administration-owned — both modules may FK to the other's tables but neither
  co-owns them. `role_master`/`permission_master`/`role_permission` are additionally sequenced
  as "Phase 0 Bootstrap RBAC" (`SOL-BOOT-001`, `BOOTSTRAP_ARCHITECTURE.md`/`SOL-ARCH-011`) —
  created before Foundation for DDL-ordering reasons; ownership doesn't change. This document
  also carries 3 explicitly **PENDING — DDL phase** design notes
  (not covered by its own FROZEN status): `ORG-PENDING-001` (organization short code, 3–5
  letters), `MEM-PENDING-001` (local Sakha number format, plus a proposed three-level Sangha
  Sevi → Sakha Affiliation → Local Number identity chain — the current
  `membership_transfer_history.old_local_sakha_number`/`new_local_sakha_number` VARCHAR fields
  are documented as insufficient for it), and `ATT-PENDING-001` (Visitor vs. Approved Darshak
  threshold — classified as an ERP operational refinement, not source-derived; no counter
  column planned, the threshold is meant to be derivable from existing attendance records).
- **Administration owns a Correspondence Register** (`CORR-DECISION-003`, `CORR-ARCH-001`/
  `002`, all FROZEN) — a generic inward/outward official-communication register
  (`correspondence`, `correspondence_document`, `correspondence_finance_reference`, plus the implemented `correspondence_sequence_counter`). Explicitly
  not a generic application/workflow engine and not an owner of the underlying business matter
  (membership renewals, property matters, governance decisions stay with their respective
  modules) or of financial transactions (Finance remains sole owner per `FIN-ARCH-001`; the
  Finance link is a reference-only M:N junction). One rule (`CORR-BR-018`, the
  `relationship_type` candidate values) is explicitly PENDING until Finance's own transaction
  taxonomy is frozen.
- **Mahila Parichalana Mandali term length disagrees across two frozen module docs.**
  `docs/03_Solution/modules/governance/04_governance_business_rules.md` (GOV-BR-036, "Mahila
  Term | FROZEN") sets the Mandali's term at **3 years**;
  `docs/03_Solution/modules/mahila/04_mahila_business_rules.md` (MAH-040, "Two-Year Term")
  freezes it at **2 years**. Both are marked FROZEN in their own module. Flagged here, not
  resolved, since picking a winner is a design decision this pass shouldn't make unilaterally.
- **`DATABASE_DESIGN_STANDARDS.md` states a business-identifier convention that contradicts the
  project's own frozen convention.** §6/§15/§21 of `docs/03_Solution/database/
  DATABASE_DESIGN_STANDARDS.md` (`SOL-DB-001`) define `_id` as the suffix for "sequential
  business identifiers" (`person_id`, `organization_id`, `sangha_sevi_id`), reserving `_code`
  for "stable classification codes" only. This directly contradicts the actual implemented SQL
  (`database/ddl/03_person/02_person.sql` uses `person_code`, not `person_id`) and the
  correction already recorded in `CLAUDE.md`. This document's own source-inventory list of
  module table-design docs suggests it absorbed the newer module docs' inconsistent `_id` usage
  (the same `person_id`/`person_code` conflict tracked for the Person module) rather than the
  actual frozen DDL convention — worth a human decision on which document is wrong before any
  new DDL is authored against `SOL-DB-001`'s stated convention. Separately, `SOL-DB-001` §31
  ("Schema Naming") also states "All tables reside in the `public` schema... No schema-per-module
  decision has been frozen" — stale since commit `764b643` namespaced every table under a
  dedicated `nss` schema (see "Database schema" above); this document needs both corrections.
- **Governance layer has an unresolved `GOV-ORG-00X` rule-ID collision, producing ambiguous
  citations.** `docs/00_Project_Governance/GOV/GOV-001_Project_Governance_Principles.md` §4 and
  `GOV-002_Organizational_Governance_Standard.md` §5 each independently define their own
  `GOV-ORG-001`–`004` (GOV-001: Statutory Authority / Governance Hierarchy / Rule Authority /
  Separation of Governance and Implementation; GOV-002: Apex Organizational Governance Principle
  / Statutory Authority Precedence / Organizational Hierarchy Integrity / Authoritative Document
  Recognition — plus GOV-001 has a 5th, `GOV-ORG-005` Traceability Principle, that GOV-002 has no
  counterpart for). `GDR-002_Creation_of_the_REF-MS_Authoritative_Reference_Family.md` (lines
  38-39) cites `GOV-ORG-001/002` and `GOV-ORG-004` meaning GOV-002's rules, while
  `GDR-004_Governance_Authority_Structure_Clarification.md` (line 55) cites `GOV-ORG-004` meaning
  GOV-001's "Separation of Governance and Implementation" — the same ID pointing at two different
  normative rules depending on which GDR you're reading. Not fixed here — renumbering either
  document's rule IDs is a governance content decision, not a drift correction; flagging only.
- **`STD/05_security_standards.md` §9's RBAC table vocabulary has drifted from both its own
  sibling standard and the implemented schema.** It lists RBAC core tables as `user_account`,
  `role`, `permission`, `role_permission`, `user_role` — but `STD/02_naming_conventions.md` §8
  mandates an `entity_master` suffix for master/lookup tables (its own sibling document's
  convention), and the actual DDL (`database/ddl/00_bootstrap/`) plus the newer
  `docs/03_Solution/security/SECURITY_ARCHITECTURE.md` §4.3 both correctly use `role_master`,
  `permission_master`, `role_permission`, `user_role`, `admin_scope`. Not fixed here — `STD/`
  is part of the frozen Governance Baseline; flagging for a human correction pass.
- **Six lifecycle documents restate Person-death-cascade rules instead of citing the existing
  lifecycle standards.** `person/03_person_lifecycle.md` (SOL-PER-005),
  `family/03_family_lifecycle.md` (SOL-FAM-005), `governance/03_governance_lifecycle.md`
  (SOL-GOV-005), `attendance/03_attendance_lifecycle.md` (SOL-ATT-006),
  `authentication/03_authentication_security_lifecycle.md` (SOL-AUTH-005), and
  `administration/03_administration_lifecycle.md` (SOL-ADMIN-005) each independently restate
  near-identical death-effect language, but none cites
  `docs/03_Solution/standards/lifecycle/PERSON_LIFECYCLE_RULES.md` (SOL-LIFE-002) or
  `PARTICIPATION_LIFECYCLE_RULES.md` (SOL-LIFE-001) as authority, even though SOL-LIFE-001 §16
  explicitly says modules "shall reference this standard rather than duplicating these rules."
  Content doesn't contradict SOL-LIFE-002 for the modules already in its consequence table
  (governance/family/attendance match it); Authentication and Administration aren't in that
  table at all, so their "not automatically deactivated" stance is a genuine gap in
  SOL-LIFE-002 rather than a contradiction. Not fixed here — editing six lifecycle docs' rule
  text is a content decision, not a drift correction.
- **Governance's and Mahila's lifecycle docs disagree on more than just term length.** Beyond
  the already-tracked 3-year vs. 2-year Mandali term conflict,
  `governance/03_governance_lifecycle.md` §33 models Mahila reconstitution as a formal
  consensus-attempt → election → `election`/`election_result`-table process, while
  `mahila/03_mahila_lifecycle.md` §24–26 describes routine reconstitution as Parichalak
  consensus + President's consent with no formal election tables at all, reserving actual
  elections for President/Vice-President vacancies only. Neither lifecycle doc reconciles this
  against the other.
- **`programmes_events/` (Module #21) is not source-aligned like its siblings, but its
  cross-module reconciliation is complete.** Unlike every other module (tagged `v1.0.0 DRAFT —
  SOURCE ALIGNED`), `programmes_events/` is v0.1.0, explicitly "FORMAL MODULE FREEZE PENDING,"
  and none of its candidate tables are frozen DDL. Its candidate-table set (`programme_type`,
  `event`, `event_day`, `event_session`, `event_registration`, `event_location`,
  `event_history`) is settled — `PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md` (`SOL-EVT-007`)
  closed all 7 gates the cross-module review had left open, including the "Ownership Ambiguity"
  risk (resolved: UPBS/Kishor/Sevak's own event entities become common-Event extensions, not
  left standalone or merely referenced) and confirming Weekly Sangha Puja stays
  Attendance-owned with no P&E dependency. Reconciliation being complete is not the same as the
  module being frozen — don't cite any table name as settled yet.
- **Mobile strategy is Flutter, not PWA.** `TECH_STACK_DECISIONS.md` §4 (`TECH-MOB-001`,
  FROZEN) targets Android + iOS from day one (Hive/Drift for offline storage, FCM for push) —
  supersedes an earlier PWA-first/Capacitor position. If any older doc or memory still says
  "PWA" for the mobile client specifically, treat it as superseded — the web app's own
  IndexedDB/Service-Worker offline support for browser-based on-site registration is unaffected
  and remains a parallel path.
- **`assets_property/` (Module #22) is the physical/administrative record of NSS property and
  assets** — `Property`/`Asset` as primary entities plus `Custodianship`/`Statutory Record`/
  `Maintenance Record`, 7 tables, 74 business rules. Tagged `v1.0.0 DRAFT — SOURCE ALIGNED`
  like most other modules (unlike Programmes & Events). Explicitly does not own financial
  transactions/depreciation (Finance), acquisition/disposal approval (Governance), or
  historical/cultural significance (Heritage) — those modules may reference the same physical
  entity without duplicating records. One rule (`AP-066`, whether "sacred articles" fall under
  this module or Heritage's model) is explicitly PENDING.
- **Two pre-DDL architecture "gates" sit on top of the unified 0–13 build order**
  (`SOL-ARCH-009`/`010`). `FK_DEPENDENCY_GRAPH.md` topologically sorts all 86 frozen tables into
  8 dependency depths (zero cycles) and resolves the audit-actor circular-dependency problem
  (`sangha_sevi` needed for audit columns everywhere, but itself depends on Foundation) via a
  two-pass DDL strategy: create tables without audit-actor FKs first, add those constraints in
  a second pass. `DDL_CREATION_ORDER.md` turns that into the exact numbered `CREATE TABLE`
  sequence. Tiers 1-2 (Foundation, Organization) have been executed against `database/ddl/`;
  Tiers 3-12 have not. `BOOTSTRAP_ARCHITECTURE.md` (`SOL-ARCH-011`) adds a "Phase 0" ahead of
  Tier 1 for the 3 RBAC tables — DDL is implemented and committed. The 7 Programmes
  & Events candidate tables are explicitly listed in both
  but marked NOT EXECUTABLE pending that module's own formal freeze.
- **Role catalogue discrepancy between the frozen design docs and the actual Bootstrap RBAC
  DDL/seed.** ~~RESOLVED~~ — `05_administration_table_design.md` §8.7 and `SOL-BOOT-001` §4.2
  now describe 8 roles / 5 scope levels, matching the DDL CHECK constraint and seed data.
  `NSS_ERP_PATHA_CHAKRA_ADMIN` / `PATHA_CHAKRA` added to the frozen catalogue.
- **Role catalogue extended again (2026-09-25), matching a governance decision on the
  organization hierarchy.** `05_administration_table_design.md` §8.7 and `SOL-BOOT-001` §4.2
  now describe **9 roles / 6 scope levels** — `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` /
  `KENDRA_MAHILA_SANGHA` added, scoped to the single organization that Organization's business
  rules now freeze as the Kendra/Central Mahila Sangha
  (`docs/03_Solution/modules/organization/04_organization_business_rules.md` §28,
  ORG-BR-087–095).
- **Role catalogue extended again (2026-10-09), implementing the §63 composite auto-grant
  rule.** `05_administration_table_design.md` §8.7 and `SOL-BOOT-001` §4.2 now describe
  **10 roles / 7 scope levels** — `NSS_ERP_ADVISORY_BOARD_ADMIN` / `ADVISORY_BOARD` added,
  held by the Advisory Board President/Secretary (auto-granted from their governance position
  via `api/services/rbac_service.py`'s `load_composite_grants()`) or a third person manually
  appointed by `NSS_ERP_ADMIN`.
- **`nss_db_backend` PostgreSQL role privileges.** ~~RESOLVED~~ — `database/scripts/04_grant_backend.sql`
  now grants `nss_db_backend` `USAGE` on schema `nss`, `SELECT` on all existing tables, and
  (via `ALTER DEFAULT PRIVILEGES`) `SELECT` on future tables — read-only, matching the FastAPI
  Tier 0 API's own read-only usage. `BOOTSTRAP_ARCHITECTURE.md` (`SOL-ARCH-011`) still only
  formalizes the `nss_db_owner`/`NSS_ERP_ADMIN` distinction and doesn't mention this role by
  name, but the privileges themselves are now defined and implemented.
- **`code_explanations/` was reorganized from per-tier to per-layer, then moved out of
  `architecture/` entirely.** The original
  `TIER0_VERTICAL_SLICE.md`/`TIER1_FOUNDATION.md`/`SECURITY_HARDENING.md` (which interleaved
  narration of the same files across multiple tier-scoped documents) were retired and replaced
  by `API_CODE_EXPLANATIONS.md`, `DATABASE_CODE_EXPLANATIONS.md`, `UI_CODE_EXPLANATIONS.md`,
  `SECURITY_CODE_EXPLANATIONS.md`, and `TESTING_CODE_EXPLANATIONS.md` — one document per layer,
  each giving every source file in that layer its own "Requirement + Line-by-line" section
  regardless of which tier introduced it. `TIER0_SECURITY_AUDIT.md`/`TIER1_SECURITY_AUDIT.md`/
  `TIER2_SECURITY_AUDIT.md` (audit findings, not code narration) were not part of this
  per-layer reorganization and still exist under their original names — **update as of Tier 4:**
  these three plus `TIER3_SECURITY_AUDIT.md` and the new `TIER4_SECURITY_AUDIT.md` have since
  all moved again, out of `code_explanations/` entirely into a dedicated
  `docs/03_Solution/security/` folder (alongside the pre-existing `SECURITY_ARCHITECTURE.md` and
  a new consolidated `SECURITY_AUDIT_TIER0_4.md`) — any reference to them still living in
  `code_explanations/` is now stale. Separately, as part of
  the Tier 2 Organization slice, the whole `code_explanations/` folder was relocated one level
  up — `docs/03_Solution/architecture/code_explanations/` → `docs/03_Solution/code_explanations/`
  — and the API contract docs were pulled out of `architecture/` into a new consolidated
  `docs/03_Solution/api/` folder (`BOOTSTRAP_API_CONTRACT.md`, `FOUNDATION_API_CONTRACT.md`,
  `ORGANIZATION_API_CONTRACT.md`, `PERSON_API_CONTRACT.md`, and a cross-tier `API_CONTRACT.md`
  added with Tier 4 — no dedicated per-tier contract exists for Family/Membership), so
  `architecture/` no longer holds either — see the
  `docs/03_Solution/` detail above for both folders' current contents. Any reference elsewhere
  (including in older commits/docs) to `docs/03_Solution/architecture/code_explanations/` or
  `docs/03_Solution/architecture/FOUNDATION_API_CONTRACT.md` is stale.
- **Filename collision in `docs/03_Solution/modules/administration/`.**
  `06_bootstrap_rbac_table_design.md` (`SOL-BOOT-001`) and `06_correspondence_register_erd.md`
  (`SOL-ADMIN-006`) share the same leading number — not renamed here, flagging only.
- **`database/migrations/` exists now, but it is not a schema-migration tool** — it holds
  exactly one file (`update_darshaka.sql`), a narrow ad-hoc data-fix script for databases
  bootstrapped before `database/seed/01_foundation/02_master_data.sql` was itself corrected to
  seed `PROBATIONARY`'s display name as `'Darshaka'` directly. Fresh `02_build.sh` runs never
  need it. This does not change the "no migration tool for this track" convention in
  `CLAUDE.md`/above — see `database/migrations/README.md`. Similarly,
  `database/seed/99_extended_test_data.sql` and `database/seed/99_fix_memberships.sql` are
  standalone, manually-run verification-data scripts living directly under `database/seed/`
  (breaking the `NN_module/` folder convention on purpose, since they're cross-cutting
  additions to already-seeded data, not a new module's own seed) — neither is run by
  `02_build.sh`.
- **Performance-hardening pass on top of Tier 4, released as v0.10.4 (merged from branch
  `performance-optimization`).** Driven by slow Family/Membership page loads after FAM-036's
  dynamic Sakha computation landed: `database/migrations/add_performance_indexes.sql` (4
  composite partial indexes on `family_relationship`, `sangha_sevi`,
  `membership_sakha_affiliation`, and `organization`, targeting the `family_majority` CTE hot
  path), wired into `database/scripts/02_build.sh`/`.ps1` and `render_build.sh` as a new "Phase
  8b — Performance Indexes" step; `render.yaml`'s start command now adds `--workers 2`;
  `api/database.py`'s connection pool `minconn` goes from 1 to 2; and `frontend/assets/js/family.js`/
  `membership.js` now fire the health-check fetch without awaiting it, with `family.js` also
  splitting its org-children fetch so the fast children list renders immediately while
  `_fetchOrgChildrenStats()` loads the heavier stats query in the background. A new
  `docs/03_Solution/architecture/PERFORMANCE_TUNING.md` documents the root-cause analysis and
  tuning rationale. **Unresolved inconsistency:** `add_performance_indexes.sql` is a schema
  change (`CREATE INDEX` statements) placed under `database/migrations/`, which — per
  `database/migrations/README.md`'s own stated convention (the bullet above) — is reserved for
  one-off *data-fix* scripts only, is supposed to never contain schema changes, and is supposed
  to never be wired into `02_build.sh`/`.ps1`/the Render build; this new file does both, directly
  contradicting that folder's documented convention. Flagged, not resolved here — the project
  maintainer needs to decide whether to move the file under `database/ddl/` or update the
  migrations README's stated convention (mirrors the `.sh`/`.ps1` parity gotcha above in spirit:
  a known, named inconsistency awaiting a decision).
- **`tests/api/test_bootstrap.py`'s exact-8-role assertions were loosened to "at least 8"/subset
  checks** — verified this is purely defensive test-robustness hardening, not a reflection of
  any actual seed-data change at the time it was written. `database/seed/00_bootstrap/
  02_role_master.sql` now seeds **10 roles** (3 SYSTEM-class + 7 ORGANIZATIONAL, after adding
  `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` on 2026-09-25 and `NSS_ERP_ADVISORY_BOARD_ADMIN` on
  2026-10-09) — the "at least N" phrasing means this didn't require touching the tests.
- **Tier 5 is a large change set, released as v0.11.0.** (See the Tier
  5 subsection under Architecture and Key Workflow #9 for the functional detail; these gotchas
  cover doc/code drift Tier 5 introduced.)
- **`database/scripts/README.md`'s Phase 13 description is now fixed** (previously didn't match
  `02_build.sh`'s actual Phase 13 — referenced nonexistent seed files and fictional `Admin@123`/
  "Ramesh Mishra" credentials). It now correctly describes `python3 scripts/bootstrap_admin.py`
  against `database/seed/04_admin/01_admin_bootstrap.sql`, seeding `P1`/`SS1` with default
  password `Admin@123` (`force_password_change = FALSE`), matching the real `02_build.sh` behavior.
- **`database/README.md` is now updated for this branch** (was previously stale — this
  documentation pass fixed it): it documents all Tier 5 tables (incl.
  `system_event_log`/`fn_audit_trigger`), the removal of `database/migrations/`,
  `database/ddl/06_authentication/`/`07_administration/`, `family_admin`,
  `darshak_attendance_registration`, `database/seed/04_admin/`, and
  `scripts/bootstrap_admin.py` — and notes that `database/fixes/` (briefly added, then
  deleted as verifiably obsolete on this same branch) no longer exists.
- **`frontend/README.md` is updated for this branch, but has fallen behind again.** It documents
  `login.html`, `register.html`, `dashboard.html`, `admin.html` (and their
  JS, plus shared `auth.js`/`nss-layout.js`), and no longer claims "Tiers 0-4 intentionally have
  no login" once Tier 5 UI exists. **`claim-approval.html` correctly does not exist as a file —
  but the feature it would have backed did ship**, as a "Registration Approvals" tab merged
  into `admin.html`/`admin.js`, and `admin.html`'s row in the File Reference doesn't mention
  that tab; the two new stylesheets `nss-layout.css`/`nss-datepicker.css` also have no entries.
- **`tests/README.md` counts were re-verified 2026-10-18** against the working tree (1118 `def test_*` functions: api 702, db 57, security 110, ui 249; `pytest --collect-only -q` = 1317 items: api 810, db 98, security 109, ui 300; collection only, tests not executed). Re-run both counts after adding tests; the session-scoped/`SAVEPOINT` `conftest.py` architecture description is still accurate.
- **Two independent "approve a pending user" code paths exist and can diverge.**
  `api/routers/claim_approval.py::approve_claim()` and
  `api/routers/admin.py::update_status()` (when activating a `PENDING_APPROVAL` account with no
  `sangha_sevi` yet) both contain their own copy of the "generate or link a `sangha_sevi_id` from
  claim data" logic — no shared helper. See Key Workflow #9.
- **The audit trail double-writes (accepted).** `api/helpers.py::log_audit()` and the DB-level
  `fn_audit_trigger()` (`database/ddl/01_foundation/15_audit_trigger.sql`, attached via a
  `DO $$` loop to every `nss.*` table except `system_event_log`/`field_change_log`) both write
  `nss.system_event_log` for plain CRUD — different row shapes, no de-duplication — because
  `log_audit()` also records semantic actions (LOGIN/APPROVE). The trigger additionally writes
  one `field_change_log` row per changed field (AUDIT-ARCH-001; exclusions: `created_at`/
  `updated_at` columns, and the `id_sequence_master`/`credential_sequence_counter` tables;
  new exclusions must be recorded in `CROSS_MODULE_PRINCIPLES.md` §7.1).
- **Audit actor lives on the write connection.** The `nss.actor_user_account_pk`/
  `nss.actor_sangha_sevi_pk` session variables are set (transaction-local) by
  `api/dependencies/auth.py::get_write_connection()`. Every router must import that dependency,
  not `api.database.get_write_connection` (the non-auditing primitive, which yields a NULL
  actor). Public endpoints legitimately write with a NULL actor; seed/admin-bootstrap rows are
  unaudited because the trigger is installed after Phase 13.
- **`api/routers/registration.py`'s `RegisterRequest.date_of_birth`/`joining_date` use a
  `Optional["date"]` forward reference resolved by a `from datetime import date` statement
  placed *after* both Pydantic model class bodies** (`api/routers/registration.py:126`) —
  works because Pydantic v2 resolves forward refs lazily at first use, not at class-body
  execution time, but it's an unusual ordering that a linter or a Pydantic version change could
  break silently.
- ~~No `permission_master`/`role_permission` seed rows are added by this branch~~ — **resolved
  since this list was written**: `database/seed/00_bootstrap/01_permission_master.sql`/
  `03_role_permission.sql` are now populated (`FOUNDATION_VIEW`/`ORGANIZATION_VIEW`/
  `PERSON_VIEW`/`PERSON_VIEW_SENSITIVE`/`FAMILY_VIEW`/`MEMBERSHIP_VIEW`/`AUDIT_VIEW` plus the
  admin/user-management set), so `require_permission(...)` calls in the new routers no longer
  403 for every role.

## Open questions / TODOs

- Correspondence Register: `tests/api/test_correspondence.py` (26), `tests/security/test_correspondence_security.py` (24) and `tests/db/test_correspondence_schema.py` (14) exist; no frontend page/UI test yet. `03_validate.sh`/`.ps1` check all 4 tables (existence, key columns, FK orphans, unique `reference_number`); the `correspondence_finance_reference.financial_transaction_pk` FK is deferred until Finance.
- **Push the `v0.11.0` tag** — created locally on `main` (`c8f2c9c`); `git push <remote> v0.11.0`, then
  publish the GitHub Release. Also run `pytest` against a rebuilt local DB (not run when cutting the release).
- ~~Reconcile `database/scripts/README.md`'s Phase 13 narrative with the actual
  `scripts/bootstrap_admin.py` behaviour~~ — **done**: the README documents the real
  seed-file paths and current default credentials (`SS1`/`P1` / `Admin@123`,
  `force_password_change = FALSE`).
- ~~Update `database/README.md` for the new Tier 5 tables~~ — **done, this documentation
  pass**: now documents all 10 (`user_account`, `password_history`, `registration_claim`,
  `password_reset_token`, `user_role`, `admin_scope`, `family_admin`,
  `darshak_attendance_registration`, `system_event_log`, `credential_sequence_counter` — the
  last one added since the original 9-table pass), 45 tables at the time (47 now, after `post_office`, `festival_master` and `festival_calendar_date`).
- ~~Update `frontend/README.md` for the new Tier 5 pages~~ — **done, an earlier documentation
  pass**:
  now documents `login.html`, `register.html`, `dashboard.html`, `admin.html` and their JS
  (plus shared `auth.js`/`nss-layout.js`/`nss-datepicker.js`/`nss-dialog.js`/`nss-location.js`)
  to the same level of detail as the Tier 0-4 pages. `claim-approval.html` is correctly **not**
  documented as a file — it doesn't exist on disk — **but the feature it would have backed did
  ship**, as a "Registration Approvals" tab merged into `admin.html`/`admin.js`; the "building
  that page... remains open" framing below is now stale and should be dropped, though
  `admin.html`'s File Reference row still doesn't mention the claims tab.
- ~~Decide whether `permission_master`/`role_permission` get seeded as part of Tier 5~~ —
  **decided and done**: they're seeded (see Gotchas above); `require_permission(...)` calls no
  longer 403-trap every role.
- **No tests yet for `POST /register/lookup-existing` and `POST /register/claim`** (grep of `tests/` finds none), nor for the `has_membership=false` registration path now creating no account.
- **Reconcile the three independent `INSERT INTO nss.sangha_sevi` code paths**
  (`claim_approval.py::approve_claim()`, `admin.py::create_user()`, `admin.py::create_sangha_sevi()`)
  into one shared helper, or explicitly decide they should stay separate because their trigger
  conditions differ.
- **Add test coverage confirming the session-scoped `SAVEPOINT` test architecture actually
  isolates modules from each other** — `tests/conftest.py`'s new design is a significant
  behavioural change (shared connection + rollback vs. independent per-module clients) with no
  meta-test verifying two modules that both mutate the same row don't leak state between runs.
- **`03_validate.sh`/`.ps1` give Family/Membership only existence checks** (Governance and Correspondence
  tables are covered; the `.ps1` lacks the Governance key-column/FK checks the `.sh` has).

- **CORS tests only exercise the unconfigured (default-empty `CORS_ORIGINS`) path** —
  `TestCORS`'s two tests assert `Access-Control-Allow-Origin` is *absent* when no origins are
  configured; there's no test setting `CORS_ORIGINS` and asserting the header *is* present for
  an allowed origin, or absent for a non-allowed one.
- **Both Security Posture Summary ASCII tables** (`TIER0_SECURITY_AUDIT.md`,
  `TIER1_SECURITY_AUDIT.md`) still list only the original 9-10 checks — neither was updated to
  add rows for the new CORS/rate-limiting/security-header protections added in
  `SECURITY_CODE_EXPLANATIONS.md`, even though the advisory tables above them were updated.
  Cosmetic, not a correctness issue.
- **Tier 4 `Family`+`Membership` is staged, committed, and released** — merged to `main` and
  tagged v0.10.0 (17 tables, 14 endpoints, 2 verification UIs, plus 166 Family+Membership tests),
  followed by hotfix tags v0.10.1-v0.10.3 and performance-hardening release v0.10.4 — see Key
  Workflow #6/"Current position" above. The
  genuine follow-up items this work left behind are tracked individually below
  (`03_validate.sh` staleness, the duplicated FAM-036 CTE, missing `/graph`/
  `/membership-summary` test coverage, stale router docstrings) rather than as one umbrella item
  — `.ps1` parity was fixed in v0.10.4.
- **`database/scripts/02_build.ps1` fixed in v0.10.4** — `02_build.sh` had gained Phases 5-9
  (Person/Family/Membership DDL + Tier 4 verification seed + grant) while the `.ps1` counterpart
  lagged behind, violating this project's own `.sh`/`.ps1` parity rule; v0.10.4 added the
  missing Phases 6-9 plus the new Phase 8b to `.ps1`, restoring parity.
- **Fix `database/scripts/03_validate.sh`/`.ps1`** — hardcodes `organization` = 3 rows,
  `person` = 0 rows, and `master_data` = 88 rows (stale — this count was captured at 82 at one
  point and has changed more than once since, verify against the live seed file rather than
  trusting this
  document); all three are now wrong (Tier 4 verification
  seed adds rows to `organization`/`person`; new `STATUS` and `ORGANIZATION_TYPE` seed values
  grow `master_data`), and there are no Family/Membership
  checks at all yet.
- ~~**Factor out the duplicated FAM-036 "effective Sakha" CTE**~~ — **fixed (Tier 5):** the
  majority-rule computation, previously implemented twice identically in
  `api/routers/organization.py`'s `/children-stats` and `api/routers/family.py`'s
  `_FAMILY_SELECT`/`/sakha-alignment`, is now a single `FAMILY_MAJORITY_CTE_SQL` constant in
  `api/helpers.py`, spliced into both call sites' own `WITH` clause.
- **Add a depth-cap guard to `/children-stats`'s recursive CTE** — unlike `/hierarchy`
  (`t.depth < 10`), `_CHILDREN_STATS_SQL` has no such guard against circular parent references.
- ~~**Add test coverage for `/families/{pk}/graph` and `/person/{pk}/membership-summary`**~~ —
  **partially fixed (Tier 5):** `tests/api/test_family_ownership.py` now covers `/graph`
  (`test_head_can_read_own_family_graph`, `test_viewer_person_pk_does_not_bypass_the_gate`).
  `/person/{pk}/membership-summary` still has zero test coverage.
- ~~**Wire `/children-stats` into the UI its own docstring claims to serve**~~ — **fixed
  (Tier 5), but in a different page than expected:** `frontend/assets/js/dashboard.js`
  (`_fetchOrgChildrenStats(orgPk)`, around line 2076) now calls it from the org family browser in
  `dashboard.html`, not from `admin.html`/`admin.js`'s Organization Hierarchy tab as the
  endpoint's own docstring still implies.
- ~~**Update stale module docstrings**~~ — `api/routers/family.py`'s docstring was updated on
  the Tier 5 (Tier 5) to "Tier 4 read-only + Tier 5 write endpoints" — no longer
  stale. `api/routers/organization.py`'s docstring now correctly says "7 GET endpoints" too
  (previously stale at "6") — this item is fully resolved.
- ~~**Fix `test_kumari_transition_has_event`**~~ — **fixed in Tier 5:**
  now `pytest.skip()`s if `SS5` isn't seeded, instead of asserting against it — no longer a
  failing test against the now seed-less database.
- ~~**Fix `test_page_loads_tailwind`/`test_page_loads_daisyui` — 10 tests**~~ — **fixed on the
  Tier 5 (Tier 5):** all 6 files' assertions now check for
  `tailwind.min.css`/`"tailwind"` (case-insensitive) instead of the old
  `cdn.tailwindcss.com`/lowercase-`daisyui` CDN strings. `test_bootstrap.py`'s UI assertions
  also now target `/bootstrap` instead of `/`, matching the new `GET /` → `/login` redirect.
- **Reconcile the "stop zero-padding IDs" decision with the actual `id_sequence_master` seed
  data** — Tier 4 introduced unpadded ID examples throughout the docs/governance baseline
  (`P1`, `SS1`, `SKH1`, `F1`) and loosened the `padding_length` CHECK constraint to allow `0`.
  Now that `next_id()` is actually wired up (see Key Workflow #3 above,
  `api/helpers.py::next_id()`), the reconciliation turned out to be moot: `next_id()` returns
  `f"{prefix}{current_value}"` — it **never reads or applies `padding_length` at all** — so
  every sequence mints unpadded IDs (`P1`, `SS12`) regardless of what its own `padding_length`
  row says. The seeded `padding_length` values (`PERSON` still 10, most others 8, `SAKHA` at 0,
  the newer `KUMARI_SANGHA`/`SEVAK_SANGHA`/`MAHILA_SANGHA` at 5) are therefore dead
  configuration as far as `next_id()`/`peek_next_id()` are concerned — `api/routers/foundation.py`
  ::`update_sequence()`'s own docstring even says padding/prefix changes only affect "IDs minted
  from now on," but no code path actually consumes `padding_length` to make that true. Either
  wire zero-padding into `next_id()` to match the column's intent, or drop the column.
- **Reconcile Family's and Membership's frozen design docs against their implemented DDL** —
  both `docs/03_Solution/modules/family/` and `docs/03_Solution/modules/membership/` remain
  `Version: 1.0, Status: DRAFT` even though their implemented DDL already matches the documented
  table/column shapes closely; unlike Person (reconciled to FROZEN v2.0.0 before its DDL
  landed), no one has done the FROZEN reconciliation pass for these two yet.
- **Decide the Organization type-to-type parent matrix** (which org types may parent which —
  e.g. does ANCHALIKA/ZILLA sit under KENDRA, does PATHA_CHAKRA sit under SAKHA or KENDRA) —
  the v1.1.0 GOVERNANCE ALIGNED business rules doc explicitly left this open rather than
  freezing it; do not treat any specific matrix as decided until this is resolved.
- **Reconcile Person's frozen design docs against the Foundation-`master_data` pattern actually
  implemented** — `docs/03_Solution/modules/person/` describes dedicated per-domain master
  tables for gender/marital_status/address_type, but the implemented DDL resolves these through
  Foundation's `master_data` instead (the same pattern already applied to Organization). This is
  the Person-side counterpart of the still-open Organization `master_data` migration Gotcha
  above — needs the same governance decision (update the frozen design docs, or treat the
  `master_data` migration as itself the frozen decision going forward).
- **Implement the `id_sequence_master` increment/formatting logic** (no function, trigger, or
  API code currently does this — see Key Workflow #3).
- **Implement the Founder & Heritage schema** — the v1.0.0 design
  (`docs/03_Solution/modules/heritage/`) specifies 8 tables; zero implementation exists (neither
  SQL DDL nor an API) for any of them.
- **Build API endpoints for `heritage`** — SQL DDL exists for none of it yet either; nothing is
  reachable over HTTP (Family and Membership, once also in this category, now have both DDL and
  a released read-only API as of v0.10.0 — see Key Workflow #6).
- **Decide the scope of `governance` and `attendance`** — Solution-layer designs exist for both,
  but no DDL or API implementation exists yet for either.
- **Build out the FastAPI application beyond Tier 0/1/2/3/4** — per `TECH_STACK_DECISIONS.md`,
  FastAPI is the approved API layer; Tier 0's 4 read-only bootstrap-RBAC endpoints, Tier 1's
  17 read-only Foundation endpoints, and Tier 2's 7 read-only Organization endpoints are all
  implemented and released (v0.7.0, v0.8.0); Tier 3's 4 read-only Person endpoints are
  released (v0.9.0); Tier 4's 7 Family + 7 Membership endpoints are implemented and released
  (v0.10.0, see "Current position" above) — every other tier's API phase
  (Heritage, Authentication, Administration, etc.) remains unbuilt.
- **Grow the frontend beyond Tier 0/1/2/3/4** — `frontend/` now has six verification UIs
  (Tailwind CSS + DaisyUI, pre-built via Tailwind CLI as of a committed change
  change — see Architecture above — + Alpine.js CDN): the Tier 0 Bootstrap Verification UI, the
  Tier 1 Foundation Verification UI, the Tier 2 Organization Verification UI, the Tier 3
  Person Verification UI, and the Tier 4 Family + Membership Verification UIs (released v0.10.0).
  None is the full admin dashboard; the 13 mockups under
  `docs/03_Solution/ui/mockups/` remain the visual target for later tiers, and login/session UI
  is deferred to Tier 5.
- **No `.env.example`** — new contributors have to reverse-engineer required env vars from
  `api/config.py`; consider adding one.
- **No formal requirements or test-plan documents exist.** `docs/02_Requirements/` and `docs/04_Testing/` were empty scaffolding and have been deleted; the test inventory is `tests/README.md`.
- **`ORG-PENDING-001` (organization short code) is frozen in `CROSS_MODULE_PRINCIPLES.md` but
  never propagated into the Organization module's own doc set.** None of
  `docs/03_Solution/modules/organization/{01_organization_module_overview,02_organization_erd,
  04_organization_business_rules,05_organization_table_design}.md` or that module's own
  `README.md` mention `organization_short_code`, `ORG-PENDING-001`, or `VARCHAR(5)` anywhere —
  the frozen column exists only in the cross-module architecture doc, not in the module that
  will actually own the column. Flagged, not fixed, since adding the column to the module's own
  design docs is itself a design-doc edit, not a drift correction.
- **Three DDL-phase design notes (`CROSS_MODULE_PRINCIPLES.md` §20-21):** `ORG-PENDING-001`
  (organization short code format, 3–5 letters) — FROZEN. `MEM-PENDING-001` (local Sakha number
  format + a proposed three-level Sangha Sevi → Sakha Affiliation → Local Number identity chain
  — likely needs a dedicated entity rather than the current inline VARCHAR fields) — PENDING.
  `ATT-PENDING-001` (Visitor vs. Approved Darshak threshold, classified ERP-operational not
  source-derived) — PENDING, non-blocking. `CORR-EXT-001` (organization-scoped correspondence
  reference numbering) — FROZEN, unblocked by the `ORG-PENDING-001` freeze. Correspondence
  format is `<ORG_SHORT_CODE>/IN/YYYY-YY/NNN` (per-organization sequences).
- **Reconcile the implemented `organization_code` column with the frozen `ORG-PENDING-001`
  spec.** `database/ddl/02_organization/03_organization.sql` defines `organization_code
  VARCHAR(10) NULL`; `ORG-PENDING-001` (`CROSS_MODULE_PRINCIPLES.md` §20.1) froze
  `organization_short_code VARCHAR(5) NOT NULL`. Different column name, different width,
  different nullability — needs an explicit decision on whether the DDL should be altered to
  match the frozen spec, or the spec updated to match what was actually built. See Key Workflow
  #4/Gotchas.
- **Reconcile seeded organization-type codes with the design docs' short forms.**
  `database/seed/01_foundation/02_master_data.sql` (formerly `database/seed/02_organization/
  01_organization_type_master.sql`, retired by the `master_data` migration) seeds
  `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA`; the Organization module's own business rules
  doc uses the short forms `ANCHALIKA`/`ZILLA`/`SAKHA` (`SAKHA_ASANA`/`PATHA_CHAKRA` already
  match). Needs a decision on which form is authoritative before this seed data or the design
  docs are extended further.
- **Seeded organization status includes `SUSPENDED`, contradicting the frozen business rule
  that excludes it.** `database/seed/01_foundation/02_master_data.sql` (formerly
  `database/seed/02_organization/02_organization_status_master.sql`, retired by the
  `master_data` migration) seeds `SUSPENDED` as one of the unified `STATUS` category's 13
  values, but `03_organization_lifecycle.md` §81 ("No Unsupported
  States") and `04_organization_business_rules.md` ORG-BR-059 ("No Unsupported Status") both
  explicitly list `SUSPENDED` as an example of a status the design does **not** introduce
  without an approved governance change. Needs a decision on whether the seed data should drop
  `SUSPENDED` or the business rule/lifecycle docs should be updated to approve it.
- **Resolve whether the two top-level `database/ddl/README.md`/`database/seed/README.md`
  files should keep existing at all.** `database/README.md`'s own execution-order section
  already covers everything they cover, via the per-module READMEs — they may be redundant
  duplication that will drift again next time a module lands. Not resolved here since deleting
  them is a structural decision, not a drift correction.
- **Reconcile `04_foundation_table_design.md`/the Foundation ERD with the implemented
  `postal_code`/`city_village_postal_code_map` tables** — these 2 tables exist in
  `database/ddl/01_foundation/` but aren't described in the Foundation module's own design docs
  (which describe 10 tables, not the 12 implemented).
- **One Correspondence Register rule is PENDING** — `CORR-BR-018`'s `relationship_type`
  candidate values for `correspondence_finance_reference` are deferred until Finance's own
  transaction taxonomy is frozen.
- **One Assets & Property rule is PENDING** — `AP-066`, whether "sacred articles" fall under
  this module's Asset-custody model or Heritage's cultural-significance model, is unresolved.
- **Formal Module #21 (Programmes & Events) freeze is the one remaining step for that module** —
  its cross-module reconciliation is complete and its candidate table set is settled at 7, but
  the module overview doc and its own README were never bumped past v0.1.0/DRAFT, and none of
  its 7 tables are frozen DDL. Reconciliation-complete is not the same as module-frozen.
- **Resolve the Mahila Parichalana Mandali term-length conflict** —
  `governance/04_governance_business_rules.md` freezes 3 years,
  `mahila/04_mahila_business_rules.md` freezes 2 years; their lifecycle docs also disagree on
  the reconstitution process itself (formal election tables vs. consensus-only). Needs an
  explicit decision on which module doc is authoritative (or a joint correction to both) before
  either is implemented — see Gotchas.
- **Add `SOL-LIFE-001`/`SOL-LIFE-002` cross-references to the six lifecycle docs** that
  currently restate death-cascade rules instead of citing them (`person`, `family`,
  `governance`, `attendance`, `authentication`, `administration`) — a future pass could add
  cross-reference notes without changing any rule content.
- **Decide which document is authoritative for the business-identifier suffix** —
  `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` (`_id`) or the implemented SQL DDL +
  `CLAUDE.md` (`_code`). Needs an explicit correction to `SOL-DB-001` (or a project-wide
  convention change, which seems unlikely given how much existing SQL/documentation already
  uses `_code`).
- ~~**Reconcile the frozen role catalogue with the actual Bootstrap RBAC implementation**~~ —
  RESOLVED. §8.7 updated to 8 roles / 5 scope levels, adding `NSS_ERP_PATHA_CHAKRA_ADMIN`.
  Docs and seed now match.
- ~~**Freeze the Organization type-to-type parent hierarchy matrix**~~ — RESOLVED
  (2026-09-25). Organization business rules §28 (ORG-BR-087–095) now freezes it; `role_master`
  gained a 9th role, `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` (9 roles / 6 scope levels), scoped to
  the newly-frozen Kendra/Central Mahila Sangha; `api/routers/admin.py`'s
  `_ALLOWED_PARENT_TYPES` and its `frontend/assets/js/admin.js` mirror were corrected to match.
- **§63 composite auto-grant rule implemented (2026-10-09).** `role_master` gained a 10th
  role, `NSS_ERP_ADVISORY_BOARD_ADMIN` (10 roles / 7 scope levels), scoped to the new
  `ADVISORY_BOARD` scope level; `body_type_master` gained 3 new body types
  (`ANCHALIKA_GOVERNING_BODY`, `ZILLA_GOVERNING_BODY`, `PATHA_CHAKRA_GOVERNING_BODY`); and
  `admin_scope`'s `chk_admin_scope_org_consistency` CHECK constraint was updated to also
  exempt `KENDRA` / `KENDRA_MAHILA_SANGHA` scope levels from requiring a non-NULL
  `organization_pk`. See `api/services/rbac_service.py`'s `load_user_context()` /
  `load_composite_grants()` for the auto-grant logic.
- ~~**Define the `nss_db_backend` PostgreSQL role**~~ — RESOLVED by
  `database/scripts/04_grant_backend.sql` (read-only `SELECT` grants). See Gotchas.
- **Resolve the `06_bootstrap_rbac_table_design.md`/`06_correspondence_register_erd.md`
  filename collision** in `docs/03_Solution/modules/administration/` — both are numbered `06`.
  See Gotchas.
- **Decide how to reconcile the `organization_type_master`/`organization_status_master`
  retirement with the frozen docs that still describe them as separate physical tables** —
  `FK_DEPENDENCY_GRAPH.md`, `DDL_CREATION_ORDER.md`, the Organization module's own v1.1.0 design
  docs, `DATABASE_DESIGN_STANDARDS.md`, and `STD/02_naming_conventions.md`/
  `03_master_data_catalog.md` all still reference both tables; the implementation now uses
  Foundation's `master_data` instead. Needs an explicit governance decision on which side
  changes. See Gotchas.
- ~~**Fix `database/scripts/03_validate.sh`'s `id_sequence_master` duplicate check**~~ — **FIXED.**
  Changed from `entity_name` to `sequence_code`.
- ~~Reconcile `database/ddl/01_foundation/README.md`'s Design Decisions with the actual `organization` table~~ — **resolved, verified this pass:** `organization` does carry `postal_code_pk` (FK to `postal_code`) and `latitude`/`longitude` `NUMERIC(10,7)`; the README was right.
- **`nss-combobox.js` is loaded but unused.** No HTML page declares `x-data="nssCombobox(...)"` yet,
  so the member-facing propose UI is not wired even though the propose endpoints and the admin
  Geo Approvals tab exist.
- **`02_build.ps1` is ported to `02_build.sh`'s existence-gated model** (`Invoke-Ddl`/`Invoke-Seed`;
  untested on Windows/PowerShell — no pwsh run yet); `03_validate.*` has only existence checks for
  Family/Membership. See `database/scripts/README.md`.
