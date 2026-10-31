# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Terse operating reference. The deep doc is `docs/PROJECT_DOCUMENTATION.md` (architecture, tier plan,
> directory detail, role/permission tables, gotchas) — read it before proposing schema/module-layout changes. Per-area detail:
> `api/README.md`, `database/README.md`, `frontend/README.md`, `tests/README.md`. Don't append
> session-by-session narrative here; permanent decisions belong in `docs/00_Project_Governance/GDR/`
> (once ratified) or the relevant module's SOLUTION doc. For what is uncommitted, run `git status` —
> Tier 5 (Authentication + Administration) is merged to `develop`/`main` and tagged `v0.11.0`;
> Tier 6 (Governance + Correspondence + Membership change requests + Attendance + Sakha re-parent approvals) is on
> `feature/tier6-governance` (16 commits past `develop`, not merged or released); the 2026-10-30/31 work (Advisory Board
> org type, null-org scopes, re-parent chain, Sakha Asana parity, address editor, Assign-Role changes) is still uncommitted on top.

## Commands

Run everything from the **repository root**.

```bash
python3 -m pip install -r requirements.txt            # Windows: py -m pip ...
python3 -m uvicorn api.main:app --reload --port 8001  # run API + frontend (Swagger at /docs)

pytest                                   # all tests (api + db + security + ui)
pytest -m integration                    # tests/api + tests/db + tests/security
pytest -m ui                             # tests/ui (Playwright browsers; the session starts its own server — NSS_UI_BASE_URL / NSS_UI_NO_SERVER=1 to use yours)
pytest tests/api/test_organization.py    # one file
pytest tests/api/test_bootstrap.py::TestHealth::test_health_returns_ok   # one test

npm install && npm run css:build         # (Node pinned in .nvmrc) only after editing Tailwind/DaisyUI classes (css:watch for dev)
```

No lint/format tooling is configured — don't add one unilaterally. Every `tests/api|db|security`
test is a real integration test (nothing mocked): it needs a bootstrapped local DB and `api/.env`.
Suite size (`pytest --collect-only -qq`, 2026-10-31): 3718 items — api 2111, db 185, security 836, ui 586. Attendance and everything written 2026-10-30/31 has **never been run against a DB** — don't claim it passes.

## Setup

`api/.env` needs `DB_NAME`/`DB_USER`/`DB_PASSWORD` (no defaults), `DB_HOST`, `DB_PORT`; for Tier 5
also `DB_WRITE_USER`/`DB_WRITE_PASSWORD` and `JWT_SECRET_KEY` (`Settings.validate_auth()` raises
otherwise; Tier 0-4 reads start without them). `database/scripts/06_setup_env.sh` (superuser)
sets all three role passwords and generates a working `api/.env`. All optional variables
(CORS, rate limit, pool sizes, `DEBUG_MODE`, `DEV_LIVE_RELOAD` (dev-only, never in deploys), CSP; `RATE_LIMIT` defaults to `300/minute`): `docs/PROJECT_DOCUMENTATION.md` → Configuration.
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

Governance DDL (10 tables, `ddl/08_governance/`) runs as build Phases 11b/11c and Correspondence DDL (5 tables incl. `correspondence_approval_step`, `ddl/09_correspondence/`; API in `correspondence.py`) as Phase 11d; Attendance DDL (4 tables, `ddl/10_attendance/`; API in `attendance.py`) as Phase 11e; Organization re-parent approval DDL (2 tables `organization_reparent_request`/`organization_reparent_step`, files `ddl/02_organization/06`-`07`, API in `org_reparent.py`) as Phase 11f (71 tables total); changing existing-table DDL (e.g. `election.election_type`, widened `admin_scope` CHECK) needs a full rebuild. Optional Phase 15 loads gitignored `seed/demo/nss_demo_seed.sql` when `RUN_DEMO_SEED` is truthy (not mirrored in `render_build.sh`).

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
permission + admin-scope loading). 17 routers, 251 endpoints (decorator-counted on `feature/tier6-governance`; 137 at v0.11.0, 12 routers); inventory: `docs/03_Solution/api/API_CONTRACT.md`.

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
- `governance.py` (Tier 6, 56 endpoints) — `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE` + org scope (`actor_scope_org_pks`/`require_org_in_scope`); `/public/*`, `/elections/open-for-voting` and `/elections/{pk}/votes/self` need login only. `NSS_ERP_ADVISORY_BOARD_ADMIN` is auto-granted by `rbac_service.load_composite_grants()` (§63), not via `user_role`.
- **NULL-organization scope levels** (GDR-005/006, status `Proposed`; resolved once in `rbac_service.actor_scope_root_org_pks()`/`actor_scope_org_pks()`, so every router inherits it): `KENDRA_MAHILA_SANGHA` reaches every `MAHILA_SANGHA` organization + subtree and holds 18 operational permissions (no `ADMIN_*`/`AUDIT_VIEW`/`FOUNDATION_MANAGE`/`PERSON_VIEW_SENSITIVE`); `ADVISORY_BOARD` reaches exactly the singleton `ADVISORY_BOARD` organization (org type #14, parent Kendra, `ADB`/`NSSAB`; its `organization_name` is immutable via `helpers.require_org_name_mutable`; owns the Advisory Board's correspondence register) and holds 8 permissions (`GOVERNANCE_VIEW/_MANAGE`, `MEMBERSHIP_VIEW`, `CORRESPONDENCE_VIEW/_MANAGE`, `ORGANIZATION_VIEW`, `FOUNDATION_VIEW`, `PERSON_VIEW`). The Advisory Board governance BODY stays NULL-organization and is NOT linked to the organization; `GOVERNANCE_MANAGE` is confined to ADVISORY_BOARD-type bodies by `governance.py::_require_scope_for_org_or_nss_wide(body_type_code=)` + `rbac_service.NULL_ORG_SCOPE_BODY_TYPES`. Existing DBs get the `role_permission` rows (166 total) via `seed/00_bootstrap/04_role_permission_mahila_advisory_board_patch.sql` and the org type + organization via `seed/02_organization/07_advisory_board_organization_patch.sql`. `UserContext.has_scope_for_org()` is the legacy exact-match probe and cannot see type-resolved reach — use `org_in_scope`/`require_org_in_scope`. `GET /governance/advisory-board/dashboard` feeds the `advisoryBoard` tab of `dashboard.html`; Correspondence org pickers use the scope-filtered `GET /organization/organizations/in-scope`. Full role/permission tables: `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas.
- `membership_change_request.py` (5 endpoints) — member-initiated Sakha Transfer / Apply for Darshak; source-release then destination-accept.
- `correspondence.py` (Tier 6, 19 endpoints) — `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE` + admin scope on `register_organization_pk` (`require_org_in_scope`/`actor_scope_org_pks`, same model as Foundation/Person/Membership). Also member-facing `my-applications`, `addressed-to-me`, `my-involvements` and a Sakha-President-then-Kendra `approval-steps/*` chain (`correspondence_approval_step`; `decide_approval_step()`). Status transitions follow the frozen §6.2 seven-row precondition table (business rules doc); reopening (ACTIONED/CLOSED → PENDING_ACTION) requires remarks (§6.3); responsible-party reassignment (§5.4) never itself transitions status. `/dispatch` and `/broadcast` are the two exceptions to the admin-scope rule — they write counterpart rows into DIFFERENT organizations' registers than the one they check scope against, by design. An OUTWARD letter to an ORGANIZATION recipient auto-mints the linked INWARD row (`_mint_inward_counterpart()`; `/dispatch` is the manual retry; the recipient-side write is a system action, not re-scoped); a reply (`in_reply_to_correspondence_pk`, an ordinary new row) auto-moves the original REGISTERED/PENDING_ACTION -> ACTIONED only under the SAME register (privilege-escalation guard — keep it); assigning a responsible party auto-moves REGISTERED -> PENDING_ACTION. ACTIONED -> CLOSED and reopening stay manual. The §5.4/§6.2 amendments are recorded in `08_correspondence_register_business_rules.md`; the circular/register-tab UI rules live in `admin.js` (`corrCanBroadcast`, `CORR_REGISTER_TAB_GROUPS`).
- `attendance.py` (Tier 6, 20 endpoints, `/api/v1/attendance`) — Weekly Sangha Puja marking: `ATTENDANCE_MANAGE`/`ATTENDANCE_VIEW` + admin scope (Sakha admin or per-Sakha `NSS_ERP_ATTENDANCE_MARKER`). Attendance Review actions and exceptions are NOT permission-gated: `_require_review_authority()` checks the live Secretary/President seat on the member's home Sakha governing body (`NSS_ERP_ADMIN` overrides). Keyed on `sangha_sevi_pk`. Tests: `tests/api/test_attendance.py`, `tests/security/test_attendance_security.py`, fixtures `tests/attendance_support.py`, UI `tests/ui/test_ui_attendance.py` — never run against a DB.
- `org_reparent.py` (4 endpoints, `/api/v1/org-reparent`, GDR-007 `Proposed`) — Sakha re-parent approvals, login-only. Chain (owner 2026-10-31): Sakha President -> LEAVING Anchalika/Zilla President (absent when the parent is Kendra) -> DESTINATION Anchalika/Zilla President -> Kendra President (final); a step with no seated President, or whose seat the requester holds, falls back to the Kendra President (consecutive Kendra steps collapse). Authority to DECIDE a step is the LIVE office seat (`api/services/seat_service.py`, incl. acting cover) — never a permission or `NSS_ERP_ADMIN`. `admin.py::update_organization` changes a Sakha's (SAKHA_SANGHA or SAKHA_ASANA) parent directly ONLY for Kendra Governing Body members (`UserContext.is_kendra_gb_member()` = §63 `NSS_ERP_KENDRA_ADMIN` composite scope) and the `NSS_ERP_ADMIN` super administrator (`is_super_admin()`, by ROLE, never a login); via `can_reparent_sakha_directly()`. Everyone else (scoped admins, office bearers, a manually-assigned non-GB Kendra Administrator) gets HTTP 202 + a request; the parent is unchanged until the chain fully approves. Logic: `api/services/org_reparent_service.py` (also owns `ALLOWED_PARENT_TYPES`). Tests: `tests/api/test_org_reparent.py`, `tests/ui/test_ui_org_reparent.py` (never run).
- `person.py` address writes (`POST/PATCH/DELETE /person/persons/{pk}/addresses[...]`) — self or `PERSON_MANAGE` in admin scope; ADDRESS_TYPE from public `GET /register/address-types`; geography must be APPROVED or the caller's own PENDING; one primary; soft delete. `admin.py::assign_role` blocks self-assignment (403) unless the caller holds `NSS_ERP_KENDRA_ADMIN` (incl. §63 auto-granted) — this includes `NSS_ERP_ADMIN`.
- **Singleton organizations** (owner 2026-10-30): at most one ACTIVE `KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`, `ADVISORY_BOARD`, and one central Mahila Sangha (`MAHILA_SANGHA` whose parent is a `KENDRA`; local per-Sakha Mahila Sanghas stay free). DB trigger `trg_enforce_organization_singleton` / `nss.fn_enforce_organization_singleton()` (`ddl/02_organization/08_organization_singleton_trigger.sql`; replaced the old ADVISORY_BOARD-only trigger; never scans existing rows, only blocks NEW offending writes) + API mirror `helpers.SINGLETON_ORG_TYPES`/`require_singleton_slot_free()` in `create_organization`/`update_organization`. Check live data with the diagnostic SELECT in `database/scripts/README.md` before the next build. A Sakha Asana without a Governing Body shell gets one from the idempotent `seed/08_governance/04_sakha_asana_governing_body_patch.sql`.
- `audit.py` — `AUDIT_VIEW`, read pool only. `field_change_log` is deliberately **not** under
  `/foundation` (enforced by a test).

**Shared code — no duplicates (standing rule).** SQL/Python/UI logic needed twice goes into one
helper — check `api/helpers.py` (catalogued in `api/README.md`) before writing new SQL/
helpers. Non-obvious ones: `SAKHA_LIKE_ORG_TYPES` (SAKHA_SANGHA + SAKHA_ASANA — a Sakha Asana is a full Sakha, owner 2026-10-31; SQL `nss.fn_is_sakha_like_org_type()`, JS `NSS.SAKHA_LIKE_ORG_TYPES`; never hard-code `'SAKHA_SANGHA'` — `tests/api/test_sakha_asana_parity.py` enforces an allow-list; the wing parents Kumari/Sevak/local Mahila/Paribarik Asana accept the whole Sakha-like set — owner 2026-10-31, GDR-008 `Proposed`, amends ORG-BR-091/092/094), `FAMILY_MAJORITY_CTE_SQL` (FAM-036 "effective Sakha" majority rule,
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
deleted; their features live in `admin.html`/`dashboard.html`). Shared: `attendance-register.js` (one attendance-marking mixin used by both `admin.js` and `org-dashboard.js`), `nss-config.js` (display
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
trailer to commits. Current state: `main` = `develop` = `99f80e6` (a docs-refresh commit past tag `v0.11.0` = `c8f2c9c`; Tier 5 released); the work is on `feature/tier6-governance` (16 commits past `develop`, unmerged; old
`feature/*` branches are merged leftovers). Don't branch a new feature off it until Tier 6 is merged.

## Open items

- **GDR-005/006/007/008 are `Proposed`** — NSS Governing Body ratification is not verified; never mark them `Approved`/`Implemented` on your own.
- Local Mahila Sangha / Paribarik Asana have a Sakha-like parent (GDR-008) but no creation path (ORG-BR-096 keeps Asana creation out of `create_organization`) — owner to decide.
- `tests/api/test_membership.py:1193` calls undefined `_get_member_by_id` (inside a `@pytest.mark.skip`-ped test; predates the 2026-10-30/31 work).
- **Advisory Board meetings & decisions are not modelled** — planned inside Programmes & Events (Module #21, not frozen); owner to specify the fields.
- `correspondence.py`: no reverse "replies to this" listing; `correspondence_finance_reference.financial_transaction_pk` FK deferred until Finance. The v1.1 `counterpart_correspondence_pk` / v1.2 `in_reply_to_correspondence_pk` columns were applied to the dev DB by live `ALTER TABLE`; a fresh/existence-gated build picks them up from the DDL file.
- Existing DBs: run the singleton diagnostic SELECT in `database/scripts/README.md` before the next build (the trigger never scans existing rows).
- `03_validate.sh`/`.ps1` check the Attendance and `organization_reparent_*` tables for existence/key columns only (no row minimums); the `.ps1` scripts have not run on Windows.
- Forgot-password OTPs are never delivered (`api/routers/auth.py` TODO) — only visible via `otp_debug`; there is deliberately no `/forgot-password` page (inline on `/login`).
- `/children-stats` and `/stats` recursive CTEs have no depth cap (`/hierarchy` caps at 10).
- `/person/{pk}/membership-summary`, `/register/lookup-existing` and `/register/claim` have no test coverage.
- `claim_approval.py::approve_claim()`, `admin.py::create_user()` and `admin.py::create_sangha_sevi()` each `INSERT INTO nss.sangha_sevi` independently — no shared helper (`update_status()` 422s on activation when the person has no active `sangha_sevi`).
- Assigning a role above the caller's own is unguarded (a Kendra Administrator can assign `NSS_ERP_ADMIN`).
- Pass 2 audit-actor FKs (`*_by_sangha_sevi_pk`) are still unconstrained on all tables.
- Deferred to later tiers: mobile/email verification, Organization contact-format CHECKs, inactive-person search, i18n, Kumari/Kishor/Sevak (Tier 9), Mahila (Tier 10).
- `PERSON_VIEW_SENSITIVE` is seeded but unwired; Aadhaar masking is unconditional.
