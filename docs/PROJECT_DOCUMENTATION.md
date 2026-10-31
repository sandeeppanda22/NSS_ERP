# NSS ERP — Project Documentation

> Standalone, code-verified reference for the NSS ERP repository. `CLAUDE.md` is the terse
> agent operating memory; `README.md` is the public pitch; per-area detail lives in
> `api/README.md`, `database/README.md`, `frontend/README.md` and `tests/README.md`. Where
> documents disagree with the code, the code wins.

## Overview

NSS ERP is an in-development ERP for **Nilachala Saraswata Sangha (NSS)**, a religious/spiritual
organization. The data model follows NSS's own statutory structure (Kendra → Anchalika/Zilla →
Sakha), its membership identity (Sangha Sevi ID), Family, Governance, Attendance, Correspondence
and (designed, not yet built) Mahila/Kumari/Kishor/Sevak Sangha, Heritage, Finance and more.

Method: **Constitution First → Governance → Requirements → Solution → Implementation**, and for
delivery **Database First → API First → UI First**, built vertically one tier at a time
(`docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md`, unified Tier 0-13 order).

What exists today:

| Layer | State |
|---|---|
| API (`api/`) | FastAPI + raw `psycopg2`, no ORM. 17 routers, 251 endpoints (decorator-counted). |
| Database (`database/`) | Hand-written PostgreSQL DDL, 71 tables in schema `nss`, no migration tool. |
| Frontend (`frontend/`) | Four static pages (`login`, `register`, `dashboard`, `admin`), Tailwind + DaisyUI + Alpine.js, served by the same FastAPI app. |
| Tests (`tests/`) | pytest, real-DB integration tests plus Playwright UI tests (3718 items collected). |
| Docs (`docs/`) | A mature governance and solution-design corpus, well ahead of the code (22 module design folders; only some are implemented). |

Not built: Flutter mobile client, Tiers 7-13 (Heritage, Programmes & Events, Kumari/Kishor/Sevak,
Mahila, Publications/UPBS, Finance, Reports/Backup), Assets & Property. Render.com + Neon.dev
deployment is declared (`render.yaml`, `render_build.sh`) but unverified in production.

### Tier status

| Tier | Scope | Status |
|---:|---|---|
| 0 | Bootstrap RBAC (`role_master`, `permission_master`, `role_permission`) | Released (v0.6.0 line) |
| 1 | Foundation (master data, geography, sequences, settings, festival calendar) | Released v0.7.0 |
| 2 | Organization | Released v0.8.0 |
| 3 | Person | Released v0.9.0 |
| 4 | Family + Membership | Released v0.10.0 (hotfixes v0.10.1-v0.10.3, performance v0.10.4) |
| 5 | Authentication + Administration + Audit | Released v0.11.0 (on `develop` and `main`) |
| 6 | Governance + Correspondence + Membership change requests + Attendance + Sakha re-parent approvals | Committed on `feature/tier6-governance` (16 commits past `develop`), **not merged or released**; the 2026-10-30/31 work (Advisory Board org type, null-org scopes, re-parent workflow, Sakha Asana parity, member address editor, Assign-Role changes) is **uncommitted** on top (`git status`) |
| 6 (rest) | Assets & Property | Design only |
| 7-13 | Heritage, Programmes & Events, Kumari/Kishor/Sevak (9), Mahila (10), Publications + UPBS, Finance, Reports + Backup | Design only |

`main` = `develop` = `99f80e6`, one docs-refresh commit past tag `v0.11.0` (= `c8f2c9c`; the tag exists
locally; confirm it is pushed before relying on it). Release notes: `docs/05_Releases/`. The
Attendance tests and every test written 2026-10-30/31 have never been run against a DB (see
`tests/README.md`).

## Architecture

```
Browser
  │
  ▼
Middleware: SlowAPI rate limit → CORS (only if configured) → security headers + CSP (api/middleware.py)
  │
  ├─ GET /, /login, /register, /dashboard, /admin   api/main.py::_serve_page() → frontend/*.html
  ├─ GET /assets/*                                  StaticFiles → frontend/assets/
  └─ /api/v1/<router>/...                           api/routers/*.py (17 routers)
        │  Depends: get_current_user / require_permission / require_org_in_scope
        │  helpers: api/helpers.py   services: api/services/
        ▼
  psycopg2 pools (api/database.py): read = nss_db_backend (SELECT only), write = nss_db_writer
        ▼
  PostgreSQL schema nss (database/ddl/, search_path = nss, public)
```

### Routers

All mounted in `api/main.py` with the prefix shown. Auth model is **per router**, not uniform.

| Router | Prefix | Endpoints | Gate |
|---|---|---:|---|
| `bootstrap.py` | `/api/v1/bootstrap` | 4 | Unauthenticated (health, roles, permissions) |
| `foundation.py` | `/api/v1/foundation` | 33 | `FOUNDATION_VIEW` reads, `FOUNDATION_MANAGE` writes; `/*/propose` needs login + active Sangha Sevi |
| `organization.py` | `/api/v1/organization` | 12 | `ORGANIZATION_VIEW` |
| `person.py` | `/api/v1/person` | 8 | `PERSON_VIEW`; detail + addresses via self-or-permission; address POST/PATCH/DELETE = self or `PERSON_MANAGE` in scope |
| `family.py` | `/api/v1/family` | 16 | Ownership model (`_require_family_view/manage/head`); `FAMILY_VIEW/MANAGE` as admin override |
| `membership.py` | `/api/v1/membership` | 9 | `MEMBERSHIP_VIEW`; detail via self-or-permission |
| `auth.py` | `/api/v1/auth` | 10 | Public login/refresh/forgot/reset; rest need login |
| `admin.py` | `/api/v1/admin` | 32 | `ADMIN_*` / `ORGANIZATION_*` permissions + admin scope |
| `registration.py` | `/api/v1/register` | 13 | Public (reference data incl. `/address-types`, register, lookup-existing, claim) |
| `claim_approval.py` | `/api/v1/admin/claims` | 5 | Permission + admin scope |
| `audit.py` | `/api/v1/audit` | 1 | `AUDIT_VIEW` (read pool) |
| `geo_approval.py` | `/api/v1/admin/geo-entries` | 4 | `FOUNDATION_MANAGE` + admin scope |
| `governance.py` | `/api/v1/governance` | 56 | `GOVERNANCE_VIEW/MANAGE` + org scope; `/public/*`, open-for-voting and `votes/self` need login only |
| `membership_change_request.py` | `/api/v1/membership/change-requests` | 5 | Member-initiated Sakha Transfer / Apply for Darshak |
| `correspondence.py` | `/api/v1/correspondence` | 19 | `CORRESPONDENCE_VIEW/MANAGE` + org scope; member-facing and approval-step endpoints |
| `attendance.py` | `/api/v1/attendance` | 20 | `ATTENDANCE_VIEW/MANAGE` + scope; review actions gated by live Secretary/President seat |
| `org_reparent.py` | `/api/v1/org-reparent` | 4 | login-only; Sakha re-parent approvals decided by live President seat (no admin override) |

Endpoint-level contract: `docs/03_Solution/api/API_CONTRACT.md`. Per-file layer reference:
`api/README.md`, `api/routers/README.md`, `api/services/README.md`.

### Layers inside `api/`

- **Routers → schemas (`api/schemas/`, Pydantic) → raw parameterized SQL.** Shared logic lives in
  `api/helpers.py` (standing rule: no duplicate SQL/Python/UI logic; check it first).
- **Services (`api/services/`):** `family_graph.py` (BFS kinship graph), `family_majority.py`,
  `family_membership.py`, `person_scope.py`, `auth_service.py` (Argon2 + JWT),
  `rbac_service.py` (`UserContext`, permission and admin-scope loading, §63 composite grants),
  `seat_service.py` (live office-seat lookups incl. acting cover; shared by Correspondence and re-parent),
  `org_reparent_service.py` (Sakha re-parent chain).
- **Dependencies (`api/dependencies/`):** `auth.py` (`get_current_user`, auditing
  `get_write_connection`) and `rbac.py` (`require_permission`, `require_any_permission`,
  `require_self_or_permission`).
- **Cross-cutting:** `config.py` (`Settings`), `database.py` (pools), `middleware.py`,
  `error_handlers.py`.

### Two DB pools and the audit actor

`api/database.py::get_connection` uses `nss_db_backend` (SELECT-only) for reads;
`get_write_connection` uses `nss_db_writer` (SELECT/INSERT/UPDATE, no DELETE, no DDL). Every
router imports the write dependency from `api/dependencies/auth.py`, **not** from `api.database`:
the former sets the `nss.actor_*` session variables on the connection the write runs on; the
latter is the non-auditing primitive and yields a NULL actor.

### Audit

Two write paths, both intentional:

1. **DB trigger `fn_audit_trigger()`** (attached to every `nss.*` table except
   `system_event_log` and `field_change_log`, created after the Phase 13 admin seed so
   bootstrap rows are unaudited) writes a row to `system_event_log` and one row per changed field
   to `field_change_log`. `field_change_log` skips the `created_at`/`updated_at` columns and the
   `id_sequence_master`/`credential_sequence_counter` tables; any new exclusion must be recorded in
   `docs/03_Solution/architecture/CROSS_MODULE_PRINCIPLES.md` §7.1.
2. **`api/helpers.py::log_audit()`** writes `system_event_log` explicitly for semantic actions
   (LOGIN, APPROVE) the trigger cannot express. Plain CRUD therefore yields two
   `system_event_log` rows of different shape — accepted.

`field_change_log` is deliberately not exposed under `/foundation` (a test enforces this); it is
read via `audit.py`.

### Middleware

Registered in `api/main.py` / `api/middleware.py`: `SlowAPIMiddleware` (one global per-IP limit,
`RATE_LIMIT`, default `300/minute`; no per-route limits), `CORSMiddleware` only when
`CORS_ORIGINS` is non-empty (GET/POST/PATCH/DELETE, credentials, never a wildcard), and security
headers (`nosniff`, `X-Frame-Options: DENY`, referrer/permissions policy, `no-store` on `/api/*`,
86400s cache on `/assets/*`) plus a Content-Security-Policy from `build_csp()`. CSP `script-src`
has no `'unsafe-inline'`, so frontend code must not use inline event handlers. HSTS is left to
the edge. Tests: `tests/security/test_security_headers.py`.

### Frontend

Static pages served by `_serve_page()`, which rewrites `/assets/*.js|css` references to
`?v=<content hash>` per request (never hand-maintain `?v=`). Mounting assets at `/assets` keeps
`/docs` and `/openapi.json` unshadowed. Pages: `login`, `register`, `dashboard` (role-aware member
dashboard: personal, family tree, membership, attendance, governance, documents, change requests),
`admin` (users, organizations, registration approvals, person/member directories, reference data,
geography, geo approvals, governance, correspondence, attendance, system settings).
Shared scripts: `auth.js` (JWT + authed fetch), `nss-config.js` (display names such as
`PROBATIONARY` → "Darshaka", badge maps), `nss-layout.js`, `org-dashboard.js` (one Alpine component,
six org-type layouts), `attendance-register.js` (one marking mixin used by `admin.js` and
`org-dashboard.js`), plus datepicker/dialog/location/password/combobox helpers. `badges.css` owns
badge classes (never redefine inline). `tailwind.min.css` is a **committed, generated** file:
rebuild it after changing any Tailwind/DaisyUI class (`npm run css:build`). The old six
Tier 0-4 verification pages are deleted; their features live in `admin`/`dashboard`. Full file
reference: `frontend/README.md`, `frontend/assets/js/README.md`, `frontend/assets/css/README.md`.

### Data layer

Hand-written DDL under `database/ddl/` (numbered module folders `00_bootstrap` … `10_attendance`),
seeds under `database/seed/`, scripts under `database/scripts/`. All tables are in schema `nss`
with explicit `nss.` prefixes; extensions (pgcrypto, pg_trgm, btree_gin, postgis) live in
`public`. Table inventory by phase: `database/README.md`. Table count by module:
Bootstrap 3, Foundation 15 (incl. `system_event_log`), Organization 3 (`organization` + the 2 re-parent approval tables), Person 2, Family 6,
Membership 16, Authentication 5, Administration 2, Governance 10, Correspondence 5, Attendance 4 = 71.

### Documentation corpus (`03_Solution/` detail)

- `docs/00_Project_Governance/{AUTH,GOV,GDR,STD}/` — frozen governance and engineering
  standards. Do not redesign without an explicit decision.
- `docs/01_Authoritative_References/` — source-faithful Bye-Law transcripts (NSS and Mahila
  Sangha; also CIRCULARS/NOTIFICATIONS/RESOLUTIONS). Never paraphrase or "correct"; the original
  PDFs are in `BY-LAW/`.
- `docs/03_Solution/` — per-module design (`modules/`, 22 folders), `architecture/`
  (`TECH_STACK_DECISIONS.md`, `IMPLEMENTATION_DEPENDENCY_ORDER.md`, `FK_DEPENDENCY_GRAPH.md`,
  `DDL_CREATION_ORDER.md`, `BOOTSTRAP_ARCHITECTURE.md`, `CROSS_MODULE_PRINCIPLES.md`,
  `GETTING_STARTED.md`, `DEPLOYMENT_PROCEDURE.md`), `api/`, `database/`, `security/`, `ui/`,
  `code_explanations/`, `standards/`, `infrastructure/`.
- `docs/05_Releases/` — release notes per version.
- `docs/03_Solution/architecture/DEVELOPER_REFERENCE_GUIDE.md` is the "which doc to read before
  coding" matrix.

Design docs describe the target; this repo's DDL/API are the current reality. Known divergences
are listed under Conventions & gotchas.

## Directory structure

```
NSS_ERP/
├── api/            FastAPI app: main.py, config.py, database.py, helpers.py, middleware.py,
│                   error_handlers.py, routers/ (17), schemas/, services/, dependencies/
├── frontend/       login|register|dashboard|admin .html + assets/{js,css,img}
├── database/
│   ├── ddl/        00_bootstrap … 10_attendance (hand-written, run by 02_build)
│   ├── seed/       reference data per module; 04_admin/ admin superuser; demo/ (gitignored)
│   └── scripts/    00_create_database.sql, 01_extensions.sql, 02_build.sh/.ps1,
│                   03_validate.sh/.ps1, 04_grant_backend.sql, 05_create_writer_role.sql,
│                   06_setup_env.sh
├── scripts/        bootstrap_admin.py (Phase 13 admin seed), backfill_sibling_links.py (one-time)
├── tests/          api/ db/ security/ ui/ + conftest.py and *_support.py shared builders
├── docs/           00_Project_Governance, 01_Authoritative_References, 03_Solution, 05_Releases
├── BY-LAW/         Original Bye-Law source documents
├── render.yaml, render_build.sh   Render/Neon deployment (declared, unverified)
├── requirements.txt, package.json, tailwind.config.js, pytest.ini
├── CLAUDE.md, README.md, NSS_ERP_PROJECT_CONTEXT.md
└── NSS LOGO/       Source logo artwork
```

Per-folder detail: [`api/README.md`](../api/README.md), [`database/README.md`](../database/README.md),
[`frontend/README.md`](../frontend/README.md), [`tests/README.md`](../tests/README.md),
[`scripts/README.md`](../scripts/README.md).

## Setup & running

Run everything from the **repository root**.

1. **Python deps:** `python3 -m pip install -r requirements.txt` (Windows: `py -m pip ...`).
   Includes FastAPI, Uvicorn, psycopg2-binary, Pydantic, python-dotenv, slowapi, argon2-cffi,
   PyJWT, pytest, httpx/httpx2 (needed by `TestClient`) and the Playwright stack.
2. **Database** (details: `database/README.md`, `database/scripts/README.md`,
   `docs/03_Solution/architecture/GETTING_STARTED.md`):
   1. `database/scripts/00_create_database.sql` (superuser) — database `nss_erp` and roles
      `nss_db_owner`, `nss_db_backend`, `nss_db_writer`.
   2. `01_extensions.sql` (superuser, on `nss_erp`) — extensions and the `nss` schema.
   3. `06_setup_env.sh` (superuser, bash) — sets all three role passwords and writes `api/.env`
      including a random `JWT_SECRET_KEY`. On Windows set passwords with `ALTER ROLE` and write
      `api/.env` by hand.
   4. `02_build.sh` / `02_build.ps1` (as `nss_db_owner`) — all DDL and seed in phase order
      (0 Bootstrap RBAC … 11e Attendance, 11f Sakha re-parent approval, 12 writer grants, 13 admin seed, 13b geo backfill,
      14 audit, optional 15 demo seed). The Foundation seed includes all-India geography, so
      Phase 2 is slow. Seeds the admin superuser via `scripts/bootstrap_admin.py` (login `SS1`/`P1`,
      password `Admin@123`; INSERT-only, never resets an existing password).
   5. `03_validate.sh` / `.ps1` — table existence, FK and row-count checks (count minimums only
      WARN; Family, Membership, `system_event_log` and `credential_sequence_counter` get existence
      checks only).
3. **Start:** `python3 -m uvicorn api.main:app --reload --port 8001`. Swagger at `/docs`
   (`DISABLE_DOCS=true` removes `/docs`, `/redoc`, `/openapi.json`). `/` redirects to `/login`.
4. **Tests:** see below. **CSS:** `npm install && npm run css:build` only after editing
   Tailwind/DaisyUI classes (`css:watch` for dev).

Build-script rules:

- `02_build.sh`/`.ps1` and `render_build.sh` are **existence-gated** per table
  (`run_ddl`/`run_seed`, `Invoke-Ddl`/`Invoke-Seed`; `to_regclass('nss.<t>')`): an existing
  table's DDL **and seed** are skipped, so only new tables get created/seeded. Editing an
  existing table's DDL or seed needs a full rebuild (or a manual `ALTER TABLE`).
- `.sh`/`.ps1` pairs must stay operationally identical (shell wrappers only). The `.ps1` port is
  untested on Windows.
- A fresh build seeds **no** Person/Family/Membership data: only reference data, 175 real Sakha
  branches and the one admin. Real data arrives via `POST /api/v1/register` → admin
  `POST /api/v1/admin/claims/{pk}/approve`.
- Grants: `nss_db_backend` read-only and `nss_db_writer` SELECT/INSERT/UPDATE on all `nss`
  tables, present and future.

### Tests

```bash
pytest                                   # all (api + db + security + ui)
pytest -m integration                    # tests/api + tests/db + tests/security
pytest -m ui                             # Playwright; needs browsers; starts its own server
pytest tests/api/test_organization.py    # one file
pytest tests/api/test_bootstrap.py::TestHealth::test_health_returns_ok   # one test
```

Markers (`pytest.ini`): `integration`, `ui`, `db`. Every `tests/api|db|security` test is a real
integration test (nothing mocked) and needs a bootstrapped DB plus `api/.env`. `tests/conftest.py`
overrides both pool dependencies to yield one session-scoped writer connection and wraps each test
module in a `SAVEPOINT` rolled back at teardown — this is why the suite passes on a seed-less DB.
An autouse fixture resets the process-wide rate-limit singleton before every test. UI tests use
`NSS_UI_BASE_URL` / `NSS_UI_NO_SERVER=1` to target an external server. `pytest --collect-only`
reports 3718 items (api 2111, db 185, security 836, ui 586); per-file counts and the not-yet-run list are in
`tests/README.md` (Attendance suites and everything written 2026-10-30/31 have never been run against a DB). No
lint/format tooling is configured.

### Deployment (Render + Neon)

`render.yaml` defines one free-tier web service (`uvicorn api.main:app --host 0.0.0.0 --port
$PORT`); the database is an external Neon instance configured through dashboard env vars.
`render_build.sh` runs `npm install` + the Tailwind build, `pip install`, then the same
phases as `02_build.sh` on every deploy (existence-gated). `RUN_DB_BOOTSTRAP` (truthy =
`true`/`1`/`yes`/`on`, default off) gates **only** the Phase 13 admin seed. Known drift: no
`postgis`, a Phase 13 failure only warns, the demo-seed Phase 15 is not mirrored, `render.yaml`
declares an unused `DATABASE_URL`, and `npm install` in a `runtime: python` service is
untested. See `docs/03_Solution/architecture/DEPLOYMENT_PROCEDURE.md`.

## Configuration

Read by `api/config.py::Settings` from `api/.env` (path is `api/.env`, not a repo-root `.env`;
UTF-8 BOM tolerated). A template is at `api/.env.example`.

| Setting | Default | Notes |
|---|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | none (required) | `Settings.validate()` raises `RuntimeError` if missing |
| `DB_HOST`, `DB_PORT` | `localhost`, `5432` | |
| `DB_WRITE_USER`, `DB_WRITE_PASSWORD`, `JWT_SECRET_KEY` | none | `Settings.validate_auth()` raises if missing; only write/auth paths call it, so read endpoints start without them |
| `DB_READ_POOL_MIN/MAX`, `DB_WRITE_POOL_MIN/MAX` | `2/15`, `1/5` | `ThreadedConnectionPool` sizes |
| `JWT_ACCESS_TOKEN_MINUTES`, `JWT_REFRESH_TOKEN_DAYS`, `JWT_ABSOLUTE_SESSION_DAYS` | `30`, `7`, `30` | Algorithm fixed `HS256`; absolute cap enforced in `decode_token()` from `session_start` |
| `CORS_ORIGINS` | empty | Comma-separated; empty means `CORSMiddleware` is never registered |
| `RATE_LIMIT` | `300/minute` | Global per-IP (`slowapi` spec) |
| `CSP_ENABLED`, `CSP_REPORT_ONLY` | `true`, `false` | Report-only emits `Content-Security-Policy-Report-Only` |
| `CSP_SCRIPT_SRC_EXTRA`, `CSP_STYLE_SRC_EXTRA` | empty | Extra CSP origins without code change |
| `DISABLE_DOCS` | `false` | Truthy removes Swagger/ReDoc/OpenAPI |
| `DEBUG_MODE` | `false` | `POST /auth/forgot-password` echoes the OTP as `otp_debug`; dev-only |
| `DEV_LIVE_RELOAD` | `false` | Dev-only: registers unauthenticated `GET /__dev/frontend-version` and injects `dev-reload.js` into pages. Never set in a deployed environment |
| `API_PORT` | `8001` | Defined but unread; the port comes from the `uvicorn` command |

Hardcoded in `Settings` (not env-configurable): lockout 5 failed attempts → 30 s auto-unlock;
password length 8-128, expiry 365 days (warning at 30); reset OTP 6 digits, 15 min expiry, max 3
active tokens, 60-minute rate window. Build-time env: `RUN_DB_BOOTSTRAP` (Render),
`RUN_DEMO_SEED` (local, loads gitignored `database/seed/demo/nss_demo_seed.sql`), `PYTHON`
override in the build scripts.

## Key workflows

### 1. Self-registration → admin approval → login

1. `register.html` fills dropdowns from the public `GET /api/v1/register/reference-data`,
   `/states`, `/districts`, `/postal-codes` (thin wrappers over the shared `fetch_*()` functions;
   a prospective member has no JWT, so the permission-gated Foundation endpoints cannot be used).
   The PIN suggestions are narrowed by the chosen **district** (`/postal-codes?district_pk=`, resolved via approved
   `city_village` rows since `postal_code` has no district column); a sparsely seeded district lists few PINs, so a
   new PIN stays enterable (free text on register, propose in the dashboard address editor).
2. `POST /api/v1/register` (`registration.py`) always creates `person` (`next_id(cur, "PERSON")`).
   Only when `has_membership` is true does it also create
   `user_account(account_status='PENDING_APPROVAL')` and a `registration_claim(PENDING)` (an
   account with no path to a Sangha Sevi could never log in). No `sangha_sevi` exists yet.
3. A membership-less registrant returns via public `POST /register/lookup-existing` (person_id +
   DOB) then `POST /register/claim`.
4. A scoped admin reviews in `admin.html` → Registration Approvals (`claim_approval.py`):
   `PATCH /{pk}` corrects fields, `POST /{pk}/approve` creates `sangha_sevi`
   (`next_id(cur, "SANGHA_SEVI")`) and `membership_sakha_affiliation` and activates the account;
   `POST /{pk}/reject` requires remarks and leaves the account `PENDING_APPROVAL`. Darshaka
   (`PROBATIONARY`) claims always get a new Sangha Sevi ID; other types must supply a local Sakha
   number that either matches that person's existing ID or becomes the new ID.
5. `admin.py::update_status` refuses to activate an account whose person has no active
   `sangha_sevi` (422), or while a PENDING claim exists.
6. `POST /api/v1/auth/login`: `login_id` is tried as `sangha_sevi_id` then `person_id`;
   `PENDING_APPROVAL` accounts are refused (403) before the password check; Argon2 verification;
   5 failures lock the account for 30 s (self-clearing, no unlock endpoint). A JWT access +
   refresh pair is issued; both carry `session_start` and are rejected after 30 days.

### 2. Request authorization (permission, ownership, admin scope)

Every protected endpoint depends on `get_current_user` (decodes the Bearer JWT) and usually
`require_permission(code)`, which calls `rbac_service.load_user_context()` — a fresh DB load per
request of the union of active roles' permissions (`user_role` → `role_permission` →
`permission_master`) plus one `ScopeInfo` per role assignment (`user_role` → `admin_scope`), plus
§63 composite grants from `load_composite_grants()`. Permission alone never confers reach:
handlers additionally call `require_org_in_scope` / `actor_scope_org_pks` /
`require_person_in_scope` / `require_account_in_scope` (ADMIN-BR-076/077), so a scoped admin only
touches organizations, persons and accounts inside their own `admin_scope` subtree;
`NSS_ERP_ADMIN` and Kendra/NSS-WIDE scope are global. Person/Membership detail routes use
`require_self_or_permission()`; Family uses its ownership model. Writes then run on the
writer connection with the audit actor set (see Architecture → Audit).

### 3. Business-ID generation

`api/helpers.py::next_id(cur, sequence_code)` atomically increments `nss.id_sequence_master`
(`UPDATE ... RETURNING`) and returns `prefix + current_value` — **unpadded** (`P1`, `SS12`,
`SKH5`, `F3`). It never reads `padding_length`; the seeded padding values are dead configuration
(either wire padding in or drop the column). Callers: registration and admin (`PERSON` and
org-type sequences), `claim_approval.approve_claim()` (`SANGHA_SEVI`), `family.create_family()`
(`FAMILY`). Related generators: `next_credential_document_number()` (Kendra/Anumati numbers via
`credential_sequence_counter`), `next_correspondence_reference_number()` (per-register /
per-direction / per-financial-year), `next_sakha_local_number()`.

Member identity is three-tier: Sangha Sevi ID (`sangha_sevi`, NSS-wide, permanent), Local Sakha
Number (`membership_sakha_affiliation.local_sakha_erp_id`, per Sakha, archived on transfer and
never reassigned), Kendra Number (`parichaya_patra.document_number`, annual, e.g.
`345/2024/2025`). Associate members get a Parichaya Patra but no Anumati Patra.

### 4. Family graph and "effective Sakha"

`family_link` stores only direct `PARENT_OF`, `SPOUSE_OF` (and `SIBLING_OF`, backfilled by
`scripts/backfill_sibling_links.py`) edges. `GET /api/v1/family/families/{pk}/graph` builds an
in-memory graph (`api/services/family_graph.py::build_family_graph()`) and
`compute_relationships()` BFS-derives every other kinship term (grandfather, aunt, in-laws) from
the viewer's perspective via the `PATH_LABELS` table — so changing the family head needs no data
re-entry. A family's "effective Sakha" follows the FAM-036 majority rule, implemented once as
`FAMILY_MAJORITY_CTE_SQL` in `api/helpers.py` and shared by organization stats and all family reads
(`/sakha-alignment` flags mismatches against members' own affiliations).

### 5. Member-assisted geography and Tier 6 workflows

- **Geography:** a logged-in member with an active Sangha Sevi proposes a missing district /
  PIN / post office / village via `POST /api/v1/foundation/{...}/propose` (stored
  `entry_status='PENDING'`); dropdowns only show `APPROVED` rows. A `FOUNDATION_MANAGE` admin
  approves or corrects in `admin.html` → Geo Approvals (`geo_approval.py`); correct
  find-or-creates the canonical row and re-points dependent `person_address` FKs. The
  `nss-combobox.js` picker is instantiated in `dashboard.html` (personal tab, Address card:
  members add/edit/remove their own addresses; district, city/village, PIN and post office are
  each select-existing or propose-new via the endpoints above).
- **Correspondence (`correspondence.py`):** per-organization register (reference format
  `<ORG_SHORT_CODE>/IN|OUT/YYYY-YY/NNN`). Status changes follow the frozen seven-row §6.2
  precondition table in `docs/03_Solution/modules/administration/08_correspondence_register_business_rules.md`;
  reopening requires remarks. An OUTWARD letter to an ORGANIZATION recipient auto-mints a linked
  INWARD row in the recipient's register (`_mint_inward_counterpart()`; `POST /{pk}/dispatch` is the
  manual retry); `POST /broadcast` sends one circular to every descendant organization of a type;
  a reply (`in_reply_to_correspondence_pk`) is an ordinary new row that links back and auto-moves
  the original to ACTIONED when under the same register; assigning a responsible party auto-moves
  REGISTERED to PENDING_ACTION. `/dispatch` and `/broadcast` are the two deliberate exceptions to
  the admin-scope rule (they write into other organizations' registers).
- **Governance (`governance.py`):** governing bodies, seats, elections, nominations, votes and
  results. `NSS_ERP_ADVISORY_BOARD_ADMIN` and other body-derived admin roles are auto-granted by
  `rbac_service.load_composite_grants()` (§63), not via `user_role`.
- **Attendance (`attendance.py`):** weekly Sangha Puja marking, keyed on `sangha_sevi_pk`; the
  attended Sakha may differ from the member's home Sakha. Review/exception actions check the live
  Secretary/President seat (`_require_review_authority()`; `NSS_ERP_ADMIN` overrides).
- **Sakha re-parenting (`org_reparent.py`, owner rule 2026-10-30):** moving a Sakha (SAKHA_SANGHA or
  SAKHA_ASANA — the owner treats them as the same; an Asana has its own Governing Body and President)
  under a different Anchalika/Zilla (the Assign Sakha action, incl. the initial move out of Kendra) is
  direct ONLY for Kendra Governing Body members — `UserContext.is_kendra_gb_member()`, i.e. the §63 composite
  `NSS_ERP_KENDRA_ADMIN` scope with `user_role_pk` None (an active/acting seat on the Kendra GB) — and
  for the `NSS_ERP_ADMIN` super administrator (`UserContext.is_super_admin()`, by role, never a hard-coded
  login); both through `UserContext.can_reparent_sakha_directly()`.
  A role-assigned (non-GB) Kendra admin, scoped admins and office bearers all file a request
  instead (`PATCH /admin/organizations/{pk}` answers HTTP 202; other fields in the PATCH apply now,
  the parent does not). Chain (owner 2026-10-31, 4 steps): the Sakha's own President -> the LEAVING
  Anchalika/Zilla President (`SOURCE_PARENT_PRESIDENT`; absent when the current parent is Kendra) ->
  the DESTINATION Anchalika/Zilla President -> the Kendra President (final). A step with no seated
  President (live seat incl. acting cover) or whose seat the requester holds is assigned to the Kendra
  President (never auto-approved/skipped); consecutive Kendra steps collapse into one. Any reject closes the request (remarks required); the
  requester, a Kendra GB member or NSS_ERP_ADMIN may cancel while pending; one open request per Sakha. The final
  approval re-validates (Sakha active, target active/allowed type/not a descendant, not already the
  parent) and applies the parent change in the same transaction, else cancels with a system remark.
  Presidents decide from Dashboard -> Pending Items. Seat lookups are shared in
  `api/services/seat_service.py` (also used by Correspondence); logic in
  `api/services/org_reparent_service.py`; tables `organization_reparent_request`/`_step` (build
  Phase 11f). Other org types still re-parent directly.
- **Membership change requests:** member-initiated Sakha Transfer / Apply for Darshak; the source
  Sakha releases, then the destination accepts.
- **Assign Role (`admin.html` modal -> `POST /admin/users/{pk}/roles`, `admin.py::assign_role()`):**
  roles show their friendly `role_name`; the Organization picker appears only for scope levels that need
  an org (`_scopeNeedsOrg`); roles the target cannot validly receive again are hidden
  (`assignableRoles`); a "Current roles" list shows what the member already holds; for a Sakha-level
  role the member's own Sakha is offered as a one-click suggestion (`roleSuggestedOrg`, from
  `organization_pk` = home Sakha on the user responses). Self-assignment is allowed only to a
  `NSS_ERP_KENDRA_ADMIN` holder (403 otherwise, incl. `NSS_ERP_ADMIN`).
- **Member address editor:** the dashboard personal tab drives `POST/PATCH/DELETE
  /person/persons/{pk}/addresses[/{address_pk}]` (self or `PERSON_MANAGE` in scope; ADDRESS_TYPE from the
  public `/register/address-types`; APPROVED-or-own-PENDING geography only; one primary address; soft
  delete) through `nss-combobox.js` + `nss-location.js` (`NSSLocation`: cascading country/state/district/
  PIN/city with stale-response guards). PIN is narrowed by `district_pk`. `admin.js` resets every child
  dropdown when its parent changes. `nss-password.js` (`x-pw-reveal`) adds the show/hide toggle to
  password inputs.


## Conventions & gotchas

### Role hierarchy by access (lowest → highest)

Derived from `database/seed/00_bootstrap/02_role_master.sql`, `03_role_permission.sql` and the idempotent
`04_role_permission_mahila_advisory_board_patch.sql` (166 `role_permission` rows). "Reach" is a
separate axis from permissions: an ORGANIZATIONAL role only acts inside its `admin_scope`
subtree; `NSS_ERP_ADMIN` and Kendra/NSS-WIDE scope are global (`UserContext.is_nss_wide()`). Two NULL-organization scope levels
are resolved in `rbac_service.actor_scope_root_org_pks()`: `KENDRA_MAHILA_SANGHA` -> every `MAHILA_SANGHA` organization + subtree;
`ADVISORY_BOARD` -> the singleton `ADVISORY_BOARD` organization (its own correspondence register; the Advisory Board governance *body* stays NULL-organization and is managed by the body-type rule only, `NULL_ORG_SCOPE_BODY_TYPES`).

| Rank | Role (display name) | `role_code` | Scope level | Perms | Permissions | Access relationship |
|---|---|---|---|---|---|---|
| 1 | Attendance Marker | `NSS_ERP_ATTENDANCE_MARKER` | SAKHA | 2 | `ATTENDANCE_MANAGE`, `ATTENDANCE_VIEW` | `ATTENDANCE_MANAGE` + `ATTENDANCE_VIEW` only; subset of every role below that holds attendance perms (Sakha Admin and up) |
| 2 | Report Viewer | `NSS_ERP_REPORT_VIEWER` | NSS-WIDE | 8 | `ATTENDANCE_VIEW`, `CORRESPONDENCE_VIEW`, `FAMILY_VIEW`, `FOUNDATION_VIEW`, `MEMBERSHIP_VIEW`, `ORGANIZATION_VIEW`, `PERSON_VIEW`, `REPORT_VIEW` | Read-only views + `REPORT_VIEW`; subset of Auditor |
| 3 | Auditor | `NSS_ERP_AUDITOR` | NSS-WIDE | 14 | `ADMIN_PERMISSION_VIEW`, `ADMIN_USER_VIEW`, `ATTENDANCE_VIEW`, `AUDIT_VIEW`, `BOOTSTRAP_VIEW`, `CORRESPONDENCE_VIEW`, `FAMILY_VIEW`, `FOUNDATION_VIEW`, `GOVERNANCE_VIEW`, `MEMBERSHIP_VIEW`, `ORGANIZATION_VIEW`, `PERSON_VIEW`, `PERSON_VIEW_SENSITIVE`, `REPORT_VIEW` | Read-only across modules + `AUDIT_VIEW`, `PERSON_VIEW_SENSITIVE`, admin user/permission views; no write permission; subset of Kendra Admin and `NSS_ERP_ADMIN` |
| 4 | Anchalika / Zilla / Patha Chakra Administrator | `NSS_ERP_ANCHALIKA_ADMIN`, `_ZILLA_ADMIN`, `_PATHA_CHAKRA_ADMIN` | ANCHALIKA / ZILLA / PATHA_CHAKRA | 15 each | `ATTENDANCE_VIEW`, `BOOTSTRAP_VIEW`, `CORRESPONDENCE_MANAGE`, `CORRESPONDENCE_VIEW`, `FAMILY_MANAGE`, `FAMILY_VIEW`, `FOUNDATION_VIEW`, `GOVERNANCE_VIEW`, `MEMBERSHIP_APPROVE`, `MEMBERSHIP_MANAGE`, `MEMBERSHIP_VIEW`, `ORGANIZATION_VIEW`, `PERSON_MANAGE`, `PERSON_VIEW`, `REPORT_VIEW` | Identical permission sets (person, family, membership incl. approve, correspondence, view modules, `ATTENDANCE_VIEW`); differ only by scope; each a subset of Sakha, Mahila and Kendra Admin |
| 5a | Kendra Mahila Sangha Administrator | `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` | KENDRA_MAHILA_SANGHA (no org; resolves to every `MAHILA_SANGHA` organization + subtree) | 18 | all of rank 4, plus `ATTENDANCE_MANAGE`, `GOVERNANCE_MANAGE`, `ORGANIZATION_MANAGE` | Kendra Administrator's operational set (its 26 minus `ADMIN_PERMISSION_VIEW`, `ADMIN_ROLE_MANAGE`, `ADMIN_SCOPE_MANAGE`, `ADMIN_USER_MANAGE`, `ADMIN_USER_VIEW`, `AUDIT_VIEW`, `FOUNDATION_MANAGE`, `PERSON_VIEW_SENSITIVE`); subset of Kendra Admin, **not** of Sakha Admin (`ORGANIZATION_MANAGE`). Reach is bounded to Mahila Sanghas (owner decision 2026-10-30), so every `*_MANAGE` grant acts only there; never holds `ADMIN_*` |
| 5b | Sakha Administrator | `NSS_ERP_SAKHA_ADMIN` | SAKHA | 18 | all of rank 4, plus `ATTENDANCE_MANAGE`, `GEO_ENTRY_APPROVE`, `GOVERNANCE_MANAGE` | The rank-4 set plus `ATTENDANCE_MANAGE`, `GOVERNANCE_MANAGE`, `GEO_ENTRY_APPROVE`; same size as 5a but incomparable with it; **not** a subset of Kendra Admin (`GEO_ENTRY_APPROVE` is held by no other role, including Kendra Admin and `NSS_ERP_ADMIN`) |
| 6 | Kendra Administrator | `NSS_ERP_KENDRA_ADMIN` | KENDRA (NSS-wide-equivalent, no org) | 26 | `ADMIN_PERMISSION_VIEW`, `ADMIN_ROLE_MANAGE`, `ADMIN_SCOPE_MANAGE`, `ADMIN_USER_MANAGE`, `ADMIN_USER_VIEW`, `ATTENDANCE_MANAGE`, `ATTENDANCE_VIEW`, `AUDIT_VIEW`, `BOOTSTRAP_VIEW`, `CORRESPONDENCE_MANAGE`, `CORRESPONDENCE_VIEW`, `FAMILY_MANAGE`, `FAMILY_VIEW`, `FOUNDATION_MANAGE`, `FOUNDATION_VIEW`, `GOVERNANCE_MANAGE`, `GOVERNANCE_VIEW`, `MEMBERSHIP_APPROVE`, `MEMBERSHIP_MANAGE`, `MEMBERSHIP_VIEW`, `ORGANIZATION_MANAGE`, `ORGANIZATION_VIEW`, `PERSON_MANAGE`, `PERSON_VIEW`, `PERSON_VIEW_SENSITIVE`, `REPORT_VIEW` | Everything `NSS_ERP_ADMIN` has except `FOUNDATION_CALENDAR_MANAGE`; includes `ADMIN_ROLE_MANAGE`/`ADMIN_SCOPE_MANAGE`/`ADMIN_USER_MANAGE` |
| 7 | NSS ERP Administrator | `NSS_ERP_ADMIN` | NSS-WIDE | 27 | all of rank 6, plus `FOUNDATION_CALENDAR_MANAGE` | Superset of every other role except for `GEO_ENTRY_APPROVE` (held only by Sakha Administrator); the only holder of `FOUNDATION_CALENDAR_MANAGE` |
| — | Advisory Board Administrator | `NSS_ERP_ADVISORY_BOARD_ADMIN` | ADVISORY_BOARD (no `organization_pk`; resolves to the singleton `ADVISORY_BOARD` organization) | 8 | `CORRESPONDENCE_MANAGE`, `CORRESPONDENCE_VIEW`, `FOUNDATION_VIEW`, `GOVERNANCE_MANAGE`, `GOVERNANCE_VIEW`, `MEMBERSHIP_VIEW`, `ORGANIZATION_VIEW`, `PERSON_VIEW` | Off the ladder (subset of Sakha, Mahila, Kendra and Admin): auto-granted at runtime to the Advisory Board President/Secretary (§63, `rbac_service.load_composite_grants()`) and manually assignable. Body side: `GOVERNANCE_MANAGE` is confined server-side to ADVISORY_BOARD-type bodies (seat assignments, acting cover, removal requests — `governance.py::_require_scope_for_org_or_nss_wide(body_type_code=)`); the Sakha-nominated MEMBER seat stays with the nominating Sakha; other bodies, body-type/position catalogues and elections are refused. `MEMBERSHIP_VIEW` is the member search used to seat officers. Organization side (owner 2026-10-30, "Advisory Board should be an org type" / "needs a correspondence register"): `CORRESPONDENCE_VIEW`/`_MANAGE` bounded by admin scope to the Advisory Board organization's own register; `ORGANIZATION_VIEW` feeds the register switcher / recipient pickers; `FOUNDATION_VIEW` supplies the mandatory Medium catalogue. `PERSON_VIEW` (owner 2026-10-30) feeds the correspondence person pickers: `GET /person/persons` is scope-filtered (empty for this role), person detail is self/relative/scope-only (403), `/person/search` is the same NSS-wide trigram search the login-only `/search-selectable` already offers. Not granted: `BOOTSTRAP_VIEW`, `REPORT_VIEW`, `ORGANIZATION_MANAGE` and every `ADMIN_*` permission |

#### What each permission means

All 28 seeded permissions (`01_permission_master.sql`), in plain language. "Held by" is from `03_role_permission.sql`; Marker = Attendance Marker, Viewer = Report Viewer, Admin = NSS ERP Administrator.

| Permission | In plain language | Held by |
|---|---|---|
| `ADMIN_PERMISSION_VIEW` | See which permissions exist and which roles have them. | Auditor, Kendra, Admin |
| `ADMIN_ROLE_MANAGE` | Give roles to users and take them away. | Kendra, Admin |
| `ADMIN_SCOPE_MANAGE` | Decide which organization a role applies to (e.g. which Sakha someone administers). | Kendra, Admin |
| `ADMIN_USER_MANAGE` | Create, deactivate, lock and unlock login accounts, and reset passwords. | Kendra, Admin |
| `ADMIN_USER_VIEW` | See the list of login accounts and their details (no changes). | Auditor, Kendra, Admin |
| `ATTENDANCE_MANAGE` | Create the weekly Sangha Puja and mark each member present, absent or excused. Does not allow reviewing or closing attendance cases; that belongs to the Sakha Secretary/President seats. | Marker, Sakha, Mahila, Kendra, Admin |
| `ATTENDANCE_VIEW` | See weekly puja events, attendance records, exceptions and reviews (no changes). | Marker, Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `AUDIT_VIEW` | See the audit trail: who changed what, and when. | Auditor, Kendra, Admin |
| `BOOTSTRAP_VIEW` | See the built-in lists of roles and permissions. | Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `CORRESPONDENCE_MANAGE` | Register letters, update them, move them through their statuses and attach documents, for the organization's own register only. | Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `CORRESPONDENCE_VIEW` | Read the letters in the organization's own register (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `FAMILY_MANAGE` | Create and edit families and who belongs to them. | Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `FAMILY_VIEW` | See families, their members and relationships (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `FOUNDATION_CALENDAR_MANAGE` | Create and edit festivals and their dates (e.g. Dola Purnima). System administrator only. | Admin |
| `FOUNDATION_MANAGE` | Edit the shared reference data and system settings (lists, locations, etc.). | Kendra, Admin |
| `FOUNDATION_VIEW` | See the shared reference data, settings and locations (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `GEO_ENTRY_APPROVE` | Approve or correct districts, PIN codes, post offices and villages that members have proposed, within one's own area. | Sakha |
| `GOVERNANCE_MANAGE` | Create and edit governing bodies, positions, office-holders, elections, nominations, votes and results. | Sakha, Mahila, Advisory Board (its own bodies only), Kendra, Admin |
| `GOVERNANCE_VIEW` | See governing bodies, office-holders and elections (no changes). | Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `MEMBERSHIP_APPROVE` | Approve new enrolments, renewals and membership changes within one's area. | Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `MEMBERSHIP_MANAGE` | Create and edit memberships, Sakha affiliations and membership cards/credentials. | Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `MEMBERSHIP_VIEW` | See memberships, affiliations, credentials and membership history (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `ORGANIZATION_MANAGE` | Create, edit and deactivate organizations (Sakhas, Zillas, etc.). | Mahila (Mahila Sanghas only), Kendra, Admin |
| `ORGANIZATION_VIEW` | See organizations, their hierarchy and statistics (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Advisory Board, Sakha, Kendra, Admin |
| `PERSON_MANAGE` | Create, edit and deactivate person records. | Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |
| `PERSON_VIEW` | See person records, except sensitive details (no changes). | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Advisory Board, Kendra, Admin |
| `PERSON_VIEW_SENSITIVE` | See sensitive identity details such as Aadhaar. (Seeded but not yet enforced; Aadhaar is currently always masked.) | Auditor, Kendra, Admin |
| `REPORT_VIEW` | See reports and dashboards. | Viewer, Auditor, Anchalika/Zilla/Patha Chakra/Mahila, Sakha, Kendra, Admin |

Only `NSS_ERP_ADMIN` and `NSS_ERP_KENDRA_ADMIN` hold `ADMIN_ROLE_MANAGE`, so only they can reach
`POST /admin/users/{pk}/roles` (`admin.py::assign_role()`). Self-assignment is blocked (403) for
everyone except a Kendra Administrator (`NSS_ERP_KENDRA_ADMIN`, incl. the §63 auto-granted one) —
owner decision 2026-10-30; this includes `NSS_ERP_ADMIN`. Still unguarded: assigning a role above
the caller's own (a Kendra Administrator can assign `NSS_ERP_ADMIN`, to self or others).
Where the ladder and a role's runtime reach disagree, the seed rows above
are the source of truth for permissions; the §63 rules are the source of truth for auto-granted roles.

### Conventions

- **Naming:** tables `snake_case`; internal PK `<entity>_pk` (UUID); FKs reference PKs, never
  business IDs; system-generated business IDs are `<entity>_id` (`person_id`, `sangha_sevi_id`,
  `family_id`, `organization_id`); short reference codes are `<entity>_code`. Business IDs are
  unpadded (`P1`, `SS1`, `SKH1`, `F1`). `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md`
  uses `_id` in its own examples for what the DDL calls `_code` — a doc-side inconsistency; follow
  the DDL pattern.
- **Audit columns:** `created_/updated_/deleted_at`, `*_by_sangha_sevi_pk`, `is_active` (soft
  delete; history is never hard-deleted). Never strip audit columns from DDL; add missing ones.
- **Two role namespaces:** `nss_db_*` are PostgreSQL roles (lowercase); `NSS_ERP_*` are
  application RBAC roles in `role_master` (uppercase). `nss_db_owner` is not `NSS_ERP_ADMIN`, and
  `NSS_ERP_ADMIN` does not bypass permission checks.
- **No duplicate code (standing rule):** SQL, Python or UI logic needed twice goes into one
  helper. Check `api/helpers.py` first (catalogued in `api/README.md`).
- **Frozen principles:** Person ≠ Member · Family First · History Never Deleted · Master Data
  Driven · By-Law Supremacy · Documentation First · Configuration Over Hardcoding · Permanent
  Business Identifiers · Soft Delete + Audit Trail · Unified Body Governance · One Person = One
  Membership = One Sangha Sevi ID. Governance (`docs/00_Project_Governance/`) and the Bye-Law
  transcripts (`docs/01_Authoritative_References/`) are frozen.
- **Git:** `feature/<work>` → verify → commit → merge into `develop` → only then branch again.
  `main` advances only via a documented release (tag + `docs/05_Releases/vX.Y.Z.md` + GitHub
  Release). Remotes: `personal` (daily dev) → PR → `org` (deploy source). No `Co-Authored-By`
  trailers.

### Gotchas

- **Tier 5 gating is per router** (see the router table). `bootstrap.py` and the public
  registration/auth endpoints are the only ones reachable without a JWT. Family's ownership model
  is deliberate, not a missing gate.
- **Organization type/status come from Foundation `master_data`** (categories `ORGANIZATION_TYPE`,
  `STATUS`), not the dedicated `organization_type_master`/`organization_status_master` tables the
  frozen Organization design (v1.1.0) and several architecture docs still describe. Likewise
  Person's gender/marital status/address type. Treat the design docs as the historical target.
- **The Advisory Board is both a governance body and an organization type (owner 2026-10-30).** `ORGANIZATION_TYPE` has 14 values: the 13 frozen ones plus the singleton `ADVISORY_BOARD` (seeded by the idempotent `seed/02_organization/07_advisory_board_organization_patch.sql`, parent = Kendra, `ADB` / short_code `NSSAB`; `admin.py::_SINGLETON_ORG_TYPES` (= `helpers.SINGLETON_ORG_TYPES`) refuses a second one like the other singletons, the DB trigger `fn_enforce_organization_singleton` enforces KENDRA/NILACHALA_KUTIRA/SMRUTI_MANDIRA/ADVISORY_BOARD and the central Kendra-parented Mahila Sangha, and it mints no sequence code). It exists to own the Advisory Board's correspondence register (reference numbers `NSSAB/{IN|OUT}/<FY>/<seq>`). The `ADVISORY_BOARD` governance *body* (`body_master`, `organization_pk` NULL, one seat per Sakha, §63 auto-grant) is deliberately NOT linked to that organization — the composite rule and nomination logic depend on it staying NULL-organization.
- **Sakha re-parent gotchas:** (1) the dev admin `SS1` holds NSS_ERP_ADMIN and is therefore EXEMPT and re-parents
  directly (decided by role, not by login — a manually-assigned non-GB Kendra Administrator still files a request); (2) a request needs a
  seated Kendra President or filing returns 422 (the final step is never skipped); (3) `create_organization`
  still sets a NEW Sakha's initial parent directly (there is no prior parent to move from); (4) a direct
  Kendra GB change cancels any open request for that Sakha as superseded; (5) the approval authority is
  recomputed live from the seat at decision time — the captured `assigned_person_pk` is display only.
- **Sakha Asana is a full Sakha** (owner 2026-10-31): `SAKHA_LIKE_ORG_TYPES` (`api/helpers.py`; SQL
  `nss.fn_is_sakha_like_org_type()` in `ddl/02_organization/10_`; JS `NSS.SAKHA_LIKE_ORG_TYPES`) covers
  SAKHA_SANGHA + SAKHA_ASANA for governing body, President, members, attendance, correspondence and
  re-parenting; never hard-code `'SAKHA_SANGHA'` (`tests/api/test_sakha_asana_parity.py` enforces an
  allow-list). The wing parents (Kumari, Sevak, local Mahila Sangha, Paribarik Asana) are the same
  Sakha-like set in `ALLOWED_PARENT_TYPES` (owner 2026-10-31, GDR-008 `Proposed`; amends ORG-BR-091/092/094);
  the Kumari/Sevak one-per-parent trigger needed no change. Still SAKHA_SANGHA-specific on purpose: ORG-BR-096
  (an Asana is never created via `create_organization`), ORG-BR-098 premises, id-sequence/code generation.
- **Null-organization scopes:** `rbac_service.NULL_ORG_SCOPE_ORG_TYPE` / `NULL_ORG_SCOPE_BODY_TYPES` map
  `KENDRA_MAHILA_SANGHA` and `ADVISORY_BOARD` to organizations/bodies; `ADVISORY_BOARD` org
  `organization_name` is immutable (`helpers.require_org_name_mutable`). Decisions are recorded in
  GDR-005/006/007/008, all status `Proposed` (NSS Governing Body ratification not verified).
- **ORG-BR-099:** Anchalika/Zilla/Patha Chakra organizations may carry country/state/district but
  never a premises address (DB-trigger enforced).
- **Search:** member search is 7-field, person search 4-field, trigram threshold 0.45;
  email-shaped input is reduced with `re.split(r'[.@]', q)[0]`.
- **Aadhaar** ciphertext/hash are never returned; masking is unconditional.
  `PERSON_VIEW_SENSITIVE` is seeded but not wired.
- **Sangha Sevi creation is split:** `sangha_sevi` is created on admin approval
  (`claim_approval.py::approve_claim()`), and also independently by `admin.py::create_user()` and
  `create_sangha_sevi()` — three `INSERT INTO nss.sangha_sevi` sites with no shared helper.
- **Role assignment guard:** only `NSS_ERP_ADMIN` and `NSS_ERP_KENDRA_ADMIN` hold
  `ADMIN_ROLE_MANAGE`; see the self-assignment paragraph above.
- **Admin bootstrap** runs after the schema exists but before the audit trigger, so the admin and
  seed rows have no audit history. `bootstrap_admin.py` needs a runtime Argon2 hash, which is why it
  is Python, not SQL.
- **Attendance:** Membership Sakha ≠ Attendance Sakha; Attendance Review is not permission-gated
  but seat-gated (see Key workflows #5).
- **CSP:** no inline event handlers anywhere in `frontend/`; add third-party origins via
  `CSP_SCRIPT_SRC_EXTRA`/`CSP_STYLE_SRC_EXTRA`.
- **Password reset OTPs are never delivered** (`api/routers/auth.py` TODO); they are visible only
  via `otp_debug` when `DEBUG_MODE` is set. There is deliberately no `/forgot-password` page — the
  flow is inline on `/login`.
- **Recursive CTEs:** `/children-stats` and `/stats` have no depth cap (`/hierarchy` caps at 10).
- **Audit-actor FKs** (`*_by_sangha_sevi_pk`) are still unconstrained on all tables (Pass 2).
- **Design-doc divergences** (not drift in code): the implemented `organization` table has
  `organization_code VARCHAR(10) NULL` and `short_code VARCHAR(5) NULL`, whereas
  `ORG-PENDING-001` froze `organization_short_code VARCHAR(5) NOT NULL`; seeded org-type codes are
  `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA` while the business rules use the short forms; the
  seeded `STATUS` category includes `SUSPENDED`, which ORG-BR-059 says is not an approved state;
  Family and Membership design docs are still `Version 1.0 DRAFT`.
- **Governance doc conflicts** (decide before implementing): Mahila Parichalana Mandali term is
  3 years in `governance/04_governance_business_rules.md` but 2 years in
  `mahila/04_mahila_business_rules.md`, and their lifecycle docs disagree on the reconstitution
  process; a `GOV-ORG-00X` rule-ID collision exists in the governance layer; two files are
  numbered `06` in `docs/03_Solution/modules/administration/`
  (`06_bootstrap_rbac_table_design.md`, `06_correspondence_register_erd.md`).
- **Programmes & Events (Module #21)** is the one module not SOURCE ALIGNED / frozen.
  `docs/03_Solution/modules/foundation/` describes 10 tables; Foundation implements more
  (e.g. `postal_code`, `city_village_postal_code_map`).

## Open questions / TODOs

**Release / process**
- Commit the uncommitted 2026-10-30/31 work (`git status`), then decide when `feature/tier6-governance`
  merges to `develop` and is released.
- Ratification of GDR-005/006/007/008 by the NSS Governing Body (still `Proposed`).
- Advisory Board meetings and decisions are not modelled (planned inside Programmes & Events, Module #21;
  owner to specify the fields).
- Existing DBs: run the diagnostic SELECT in `database/scripts/README.md` for duplicate singleton
  organizations before the next build (the singleton trigger never scans existing rows).
- Run `pytest` against a freshly built DB: Attendance API/security tests and several newer test
  classes were written but never run (`tests/README.md`).
- Confirm the `v0.11.0` tag and GitHub Release are pushed.
- Local Mahila Sangha and Paribarik Asana now have a Sakha-like parent (GDR-008) but no creation path: ORG-BR-096 keeps Asana/Sakha creation out of the standard `create_organization` flow. Owner to decide how they are created.
- Stale test fixture: `tests/api/test_membership.py:1193` calls undefined `_get_member_by_id` inside `test_kumari_transition_has_event`; it is `@pytest.mark.skip`-ped, so it never fails, but it predates and is unrelated to the 2026-10-30/31 work.

**Code**
- Share one helper for the three `INSERT INTO nss.sangha_sevi` paths, or decide they stay separate.
- Either apply `padding_length` in `next_id()` or drop the column.
- Cap recursion depth in `/children-stats` and `/stats`.
- Constrain the `*_by_sangha_sevi_pk` audit-actor FKs.
- Assigning a role above the caller's own is unguarded (a Kendra Administrator can assign
  `NSS_ERP_ADMIN`).
- Deliver forgot-password OTPs (email/SMS).
- Run the newly written tests (SAVEPOINT isolation `tests/api/test_savepoint_isolation.py`, CORS `tests/security/test_cors_configured.py`, public-surface class in `tests/security/test_registration_security.py`) — written 2026-10-30, collected but never executed against a DB.
- Wire `PERSON_VIEW_SENSITIVE` or drop it.
- Correspondence: the `correspondence_finance_reference.financial_transaction_pk` FK is deferred
  until Finance; `CORR-BR-018` relationship types are PENDING; there is no reverse "replies to
  this" listing.
- `03_validate.sh`/`.ps1` stay existence-only for Family/Membership (intentional). `02_build.ps1` and `03_validate.ps1` have not been run on Windows.
- Keep `render_build.sh` in sync with `02_build.sh`: phase/file order is currently identical (checked 2026-10-30); remaining differences are intentional (see Setup).

**Design / governance decisions**
- Reconcile `organization_code`/`short_code`, org-type short forms and `SUSPENDED` with the frozen
  Organization docs, or update those docs (see Gotchas).
- Reconcile frozen docs that still describe `organization_type_master`/`organization_status_master`
  (`FK_DEPENDENCY_GRAPH.md`, `DDL_CREATION_ORDER.md`, `STD/02_naming_conventions.md`,
  `STD/03_master_data_catalog.md`) and Person's per-domain master tables with the `master_data`
  implementation.
- Freeze Family and Membership design docs against their implemented DDL.
- Decide the authoritative business-identifier suffix for `DATABASE_DESIGN_STANDARDS.md`.
- Resolve the Mahila term-length conflict, the `GOV-ORG-00X` collision and the duplicate `06`
  filename.
- Pending rules: `MEM-PENDING-001` (local Sakha number format / identity chain),
  `ATT-PENDING-001` (Visitor vs. approved Darshak threshold), `AP-066` (sacred articles:
  Assets vs. Heritage).
- Freeze Module #21 (Programmes & Events).
- Add `SOL-LIFE-001`/`SOL-LIFE-002` cross-references to the six lifecycle docs that restate the
  death-cascade rules.
- Deferred to later tiers: mobile/email verification, Organization contact-format CHECKs,
  inactive-person search, i18n, Kumari/Kishor/Sevak (Tier 9), Mahila (Tier 10).
