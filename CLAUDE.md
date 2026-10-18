# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Terse operating reference. The deep doc is `docs/PROJECT_DOCUMENTATION.md` (architecture, tier plan,
> directory detail, gotchas) — read it before proposing schema/module-layout changes. Per-area detail:
> `api/README.md`, `database/README.md`, `frontend/README.md`, `tests/README.md`. Don't append
> session-by-session narrative here; permanent decisions belong in `docs/00_Project_Governance/GDR/`
> (once ratified) or the relevant module's SOLUTION doc. For what is uncommitted, run `git status` —
> Tier 5 (Authentication + Administration) is merged to `develop`/`main` and tagged `v0.11.0`;
> Tier 6 (Governance) is in progress, uncommitted on `feature/tier6-governance`
> (tag is local only until pushed; `git push <remote> v0.11.0`).

## Commands

Run everything from the **repository root**.

```bash
python3 -m pip install -r requirements.txt            # Windows: py -m pip ...
python3 -m uvicorn api.main:app --reload --port 8001  # run API + frontend (Swagger at /docs)

pytest                                   # all tests (api + db + security + ui)
pytest -m integration                    # tests/api + tests/db + tests/security
pytest -m ui                             # tests/ui (Playwright; needs browsers + running app)
pytest tests/api/test_organization.py    # one file
pytest tests/api/test_bootstrap.py::TestHealth::test_health_returns_ok   # one test

npm install && npm run css:build         # only after editing Tailwind/DaisyUI classes (css:watch for dev)
```

No lint/format tooling is configured — don't add one unilaterally. Every `tests/api|db|security`
test is a real integration test (nothing mocked): it needs a bootstrapped local DB and `api/.env`.

## Setup

`api/.env` needs `DB_NAME`/`DB_USER`/`DB_PASSWORD` (no defaults), `DB_HOST`, `DB_PORT`; for Tier 5
also `DB_WRITE_USER`/`DB_WRITE_PASSWORD` and `JWT_SECRET_KEY` (`Settings.validate_auth()` raises
otherwise; Tier 0-4 reads start without them). `database/scripts/06_setup_env.sh` (superuser)
sets all three role passwords and generates a working `api/.env`. All optional variables
(CORS, rate limit, pool sizes, `DEBUG_MODE`, CSP): `docs/PROJECT_DOCUMENTATION.md` → Configuration.
CSP `script-src` has no `'unsafe-inline'`, so the frontend must not use inline event handlers.

## Database

Hand-written PostgreSQL DDL in `database/ddl/` (numeric folder order), run with `psql`; no
migration tool, no ORM. All tables live in schema `nss` (`search_path` = `nss, public`). Bootstrap:

1. `database/scripts/00_create_database.sql` (superuser) — DB + roles `nss_db_owner`,
   `nss_db_backend`, `nss_db_writer`; set passwords with `ALTER ROLE`.
2. `01_extensions.sql` (superuser) — pgcrypto/pg_trgm/btree_gin/postgis, `nss` schema.
3. `02_build.sh`/`.ps1` (as `nss_db_owner`) — all DDL + seed in phase order (phase/table
   inventory: `database/README.md`). `02_build.sh`/`.ps1` (and `render_build.sh`) are **existence-gated**
   (`run_ddl`/`run_seed`, `Invoke-Ddl`/`Invoke-Seed` in the `.ps1`; `to_regclass('nss.<t>')`): an existing
   table's DDL **and seed** are skipped, so only new tables get created/seeded — editing an existing
   table's DDL/seed needs a full rebuild. Also grants `nss_db_backend` read-only and
   `nss_db_writer` SELECT/INSERT/UPDATE on all `nss` tables (incl. future ones; no DELETE, no
   DDL), and seeds the admin superuser via `scripts/bootstrap_admin.py` (needs a runtime Argon2
   hash; default login `SS1`/`P1`, password `Admin@123`; INSERT-only with `WHERE NOT EXISTS`,
   never resets an existing password).
4. `03_validate.sh`/`.ps1` — row-count/FK checks (minimums only WARN, never fail);
   Family/Membership/`system_event_log`/`credential_sequence_counter` get existence checks only.

Governance DDL (10 tables, `ddl/08_governance/`) runs as build Phases 11b/11c and Correspondence DDL (4 tables, `ddl/09_correspondence/`; API in `correspondence.py`) as Phase 11d; changing existing-table DDL (e.g. `election.election_type`, widened `admin_scope` CHECK) needs a full rebuild. Optional Phase 15 loads gitignored `seed/demo/nss_demo_seed.sql` when `RUN_DEMO_SEED` is truthy (not mirrored in `render_build.sh`).

A fresh build seeds **no demo Person/Family/Membership data** — only reference data, 175 real
Sakha branches and the one admin. Real data arrives via `POST /api/v1/register` → admin
`POST /api/v1/admin/claims/{pk}/approve`.

- `.sh`/`.ps1` script pairs must stay operationally identical (shell wrappers only).
- **`render_build.sh` (repo root) duplicates the build sequence for Render/Neon** — keep it in
  sync with `02_build.sh`. `RUN_DB_BOOTSTRAP` (truthy = `true`/`1`/`yes`/`on`, case/whitespace-insensitive; default off) gates **only** Phase 13 (admin seed); all DDL/seed phases run every deploy, existence-gated. Known drift: no `postgis`, a Phase 13 failure only warns, `render.yaml` declares an unused `DATABASE_URL`, and
  `npm install` in a `runtime: python` service is untested.
- `nss_db_*` = PostgreSQL roles (lowercase); `NSS_ERP_*` = application RBAC roles in
  `role_master` (uppercase) — separate security boundaries.
- Naming: tables `snake_case`; internal PK `_pk`; FKs reference PKs, never business IDs; business
  IDs `_id` (`person_id`, `sangha_sevi_id`), codes `_code`. Business IDs are unpadded (`P1`,
  `SS1`, `SKH1`, `F1`). Audit columns `created_/updated_/deleted_at` + `*_by_sangha_sevi_pk` +
  `is_active` (soft delete; history is never hard-deleted).

## Architecture

FastAPI + raw psycopg2 (`api/`), static Tailwind/DaisyUI/Alpine frontend served by the same app
(`frontend/`). Routers → `api/schemas/` (Pydantic) with shared logic in `api/helpers.py` and
`api/services/` (`family_graph.py` BFS, `auth_service.py` Argon2/JWT, `rbac_service.py`
permission + admin-scope loading). 15 routers, 201 endpoints (Tier 6 working tree; 137 at v0.11.0); inventory: `docs/03_Solution/api/API_CONTRACT.md`.

**Two DB pools** (`api/database.py`): `get_connection` = `nss_db_backend` (SELECT-only) for reads;
`get_write_connection` = `nss_db_writer` for every write endpoint. `tests/conftest.py` overrides
both to yield one session-scoped writer connection, wrapping each test module in a `SAVEPOINT`
rolled back at teardown — that is what lets the suite pass on a seed-less DB.

**Auth model is per-router, not uniform** — check before adding an endpoint:
- `bootstrap.py` — the only unauthenticated router (plus the public `registration.py` endpoints, incl. `/register/lookup-existing` + `/register/claim`).
- `foundation`/`organization`/`person`/`membership` list endpoints — `require_permission("<MODULE>_VIEW")`
  (`api/dependencies/rbac.py`); Foundation writes need `FOUNDATION_MANAGE`.
- Person/Membership detail + sub-resources — `get_current_user` + `require_self_or_permission()`
  (a person may view their own record).
- `family.py` — all 16 endpoints use an ownership model (`_require_family_view/manage/head`,
  reached via `family_relationship`/`family_admin`), with `FAMILY_VIEW`/`FAMILY_MANAGE` as admin
  override. Deliberate; not a missing gate.
- `admin.py`/`claim_approval.py` — permission gates plus **admin scope** (`admin_scope` subtree,
  ADMIN-BR-076/077): scoped admins only touch organizations/persons/accounts inside their own
  subtree; `NSS_ERP_ADMIN`/NSS-WIDE is global. Permission alone never confers global reach.
- `geo_approval.py` (`/admin/geo-entries`) — `FOUNDATION_MANAGE` + admin scope; members propose geography via `POST /foundation/*/propose` (`get_current_user`, active Sangha Sevi required).
- `governance.py` (Tier 6, 46 endpoints) — `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE` + org scope (`actor_scope_org_pks`/`require_org_in_scope`); `/public/*`, `/elections/open-for-voting` and `/elections/{pk}/votes/self` need login only. `NSS_ERP_ADVISORY_BOARD_ADMIN` is auto-granted by `rbac_service.load_composite_grants()` (§63), not via `user_role`.
- `membership_change_request.py` (5 endpoints) — member-initiated Sakha Transfer / Apply for Darshak; source-release then destination-accept.
- `correspondence.py` (Tier 6, 9 endpoints) — `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE` + admin scope on `register_organization_pk` (`require_org_in_scope`/`actor_scope_org_pks`, same model as Foundation/Person/Membership). Status transitions follow the frozen §6.2 seven-row precondition table (business rules doc); reopening (ACTIONED/CLOSED → PENDING_ACTION) requires remarks (§6.3); responsible-party reassignment (§5.4) never itself transitions status.
- `audit.py` — `AUDIT_VIEW`, read pool only. `field_change_log` is deliberately **not** under
  `/foundation` (enforced by a test).

**Shared code — no duplicates (standing rule).** SQL/Python/UI logic needed twice goes into one
helper — check `api/helpers.py` (catalogued in `api/README.md`) before writing new SQL/
helpers. Non-obvious ones: `FAMILY_MAJORITY_CTE_SQL` (FAM-036 "effective Sakha" majority rule,
shared by organization stats and all family reads), `next_id()` (atomic `id_sequence_master`
counter; ignores `padding_length`), `next_credential_document_number()` (Kendra/Anumati numbers
via `credential_sequence_counter`), and the `fetch_*()` reference-data functions that the public
`registration.py` endpoints reuse.

**Audit has two write paths:** the DB trigger `fn_audit_trigger()` (attached to `nss.*` tables
except `system_event_log`/`field_change_log`, runs after Phase 13 so admin-bootstrap and seed
rows are unaudited) writes **both** logs — one row-level event to `system_event_log`, plus
field-level rows to `field_change_log` (one per field, for CREATE/UPDATE/DELETE; AUDIT-ARCH-001,
complete and exclusion-defined). `api/helpers.py::log_audit()` additionally writes
`system_event_log` explicitly, so plain CRUD yields duplicate rows of different shape — accepted,
since `log_audit()` also carries semantic actions (LOGIN/APPROVE) the trigger can't express.

Actor identity comes from the `nss.actor_*` session variables, set on the **write** connection by
`api/dependencies/auth.py::get_write_connection()` — every router imports the write-connection
dependency from there, **not** from `api.database` (that one is the non-auditing primitive and
yields a NULL actor). The variables must be set on the connection the write runs on, or the
trigger sees NULL.

`field_change_log` exclusions: the `created_at`/`updated_at` columns everywhere, plus the
`id_sequence_master`/`credential_sequence_counter` tables wholesale (counter churn). Excluded
tables still get their `system_event_log` row. Any new exclusion must be recorded in
`CROSS_MODULE_PRINCIPLES.md` §7.1, never added silently.

**Middleware** (`api/middleware.py`): security headers, `no-store` on `/api/*`, 86400s cache on
`/assets/*`, CORS (GET/POST/PATCH/DELETE), SlowAPI rate limiting, CSP.

**Frontend:** pages `login`/`register`/`dashboard`/`admin` (the six Tier 0-4 verification pages are
deleted; their features live in `admin.html`/`dashboard.html`). Shared: `nss-config.js` (display
names e.g. `PROBATIONARY` → "Darshaka", badge maps), `badges.css` (never redefine badge classes
inline), `auth.js` (JWT + authed fetch), `nss-layout.js`, `org-dashboard.js` (one Alpine component
for six org-type layouts). `api/main.py::_serve_page()` rewrites `/assets/*.js|css` references to
`?v=<content hash>` per request — never hand-maintain `?v=`. `tailwind.min.css` is a **committed,
generated** file: rebuild it after changing any Tailwind/DaisyUI class in HTML or JS.

**Governance is frozen** (`docs/00_Project_Governance/{AUTH,GOV,GDR,STD}/`) — don't redesign without
an explicit decision. `docs/01_Authoritative_References/` holds source-faithful Bye-Law
transcripts — never paraphrase or "correct". Frozen principles: Person ≠ Member · Family First ·
History Never Deleted · Master Data Driven · By-Law Supremacy · Documentation First ·
Configuration Over Hardcoding · Permanent Business Identifiers · Soft Delete + Audit Trail ·
Unified Body Governance · One Person = One Membership = One Sangha Sevi ID.

**Domain decisions to remember:** three-tier member identity — Sangha Sevi ID (`sangha_sevi`,
NSS-wide), Local Sakha Number (`membership_sakha_affiliation.local_sakha_erp_id`, per Sakha,
archived on transfer never reassigned), Kendra Number (`parichaya_patra.document_number`, annual,
e.g. `345/2024/2025`). Associate members get a Parichaya Patra but no Anumati Patra. Self-
registration (`POST /register`) always creates `person`, but `user_account(PENDING_APPROVAL)` +
`registration_claim` only when `has_membership` is true (an account with no path to a Sangha Sevi
can never log in); a membership-less registrant returns later via public `POST /register/lookup-existing`
+ `/register/claim` (person_id + DOB). `sangha_sevi` is created on admin approval, and
`admin.py::update_status` refuses to activate an account whose person has no active `sangha_sevi`. ORG-BR-099: Anchalika/Zilla/Patha Chakra may carry country/state/district but never
a premises address (DB-trigger enforced). Member search is 7-field, person search 4-field, trigram
threshold 0.45 with `re.split(r'[.@]', q)[0]` for email-shaped input.

## Git

`feature/<work>` → verify → commit → merge into `develop` → only then branch again. `main` advances
only via a documented release (tag + `docs/05_Releases/vX.Y.Z.md` + GitHub Release). Verify the
branch with `git status` before changes. Remotes: `personal` (daily dev) → PR → `org` (deploy
source); pushes are often blocked in-sandbox, so push from a terminal. Never add a `Co-Authored-By`
trailer to commits. Current state: `main` = `develop` = `v0.11.0` (Tier 5 released; old
`feature/*` branches are merged leftovers) — branch the next feature from `develop`.

## Open items

- `correspondence.py` has no frontend page/tab yet (nothing in `frontend/` references it), so there is
  no `tests/ui/` coverage for it — add one once the Correspondence UI is built, verifying real
  selectors first per the UI-test convention the other `tests/ui/test_ui_admin_*.py` files follow.
- There is deliberately no `/forgot-password` page (the flow is inline on `/login`); forgot-password
  OTPs are never delivered (`api/routers/auth.py` TODO) — only visible via `otp_debug`.
- `/children-stats` and `/stats` recursive CTEs have no depth cap (`/hierarchy` caps at 10).
- `/person/{pk}/membership-summary`, `/register/lookup-existing` and `/register/claim` have no test coverage.
- `claim_approval.py::approve_claim()`, `admin.py::create_user()` and `admin.py::create_sangha_sevi()`
  each `INSERT INTO nss.sangha_sevi` independently — no shared helper. (`admin.py::update_status()`
  no longer provisions one; it 422s on activation when the person has no active `sangha_sevi`.)
- Pass 2 audit-actor FKs (`*_by_sangha_sevi_pk`) are still unconstrained on all tables.
- Deferred to later tiers: mobile/email verification, Organization contact-format CHECKs,
  inactive-person search, i18n, Governance (Tier 6), Kumari/Kishor/Sevak (Tier 9), Mahila (Tier 10).
- `PERSON_VIEW_SENSITIVE` is seeded but unwired; Aadhaar masking is unconditional.
