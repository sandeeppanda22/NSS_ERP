# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Terse operating reference. The deep doc is `docs/PROJECT_DOCUMENTATION.md` (architecture, tier plan,
> directory detail, gotchas) — read it before proposing schema/module-layout changes. Per-area detail:
> `api/README.md`, `database/README.md`, `frontend/README.md`, `tests/README.md`. Don't append
> session-by-session narrative here; permanent decisions belong in `docs/00_Project_Governance/GDR/`
> (once ratified) or the relevant module's SOLUTION doc. For what is uncommitted, run `git status` —
> Tier 5 (Authentication + Administration) is merged to `develop`/`main` and tagged `v0.11.0`;
> Tier 6 (Governance + Correspondence + Membership change requests + Attendance) is committed (core) on
> `feature/tier6-governance` (5 commits past `develop`, not yet merged); Attendance and later
> Tier 6 follow-ups are still uncommitted on top of it.

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
Suite size (`pytest --collect-only -qq`, 2026-10-28): 1638 items — api 965, db 98, security 199, ui 376.

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

Governance DDL (10 tables, `ddl/08_governance/`) runs as build Phases 11b/11c and Correspondence DDL (5 tables incl. `correspondence_approval_step`, `ddl/09_correspondence/`; API in `correspondence.py`) as Phase 11d; Attendance DDL (4 tables, `ddl/10_attendance/`; API in `attendance.py`) as Phase 11e (69 tables total); changing existing-table DDL (e.g. `election.election_type`, widened `admin_scope` CHECK) needs a full rebuild. Optional Phase 15 loads gitignored `seed/demo/nss_demo_seed.sql` when `RUN_DEMO_SEED` is truthy (not mirrored in `render_build.sh`).

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
permission + admin-scope loading). 16 routers, 241 endpoints (working tree, decorator-counted; 137 at v0.11.0); inventory: `docs/03_Solution/api/API_CONTRACT.md`.

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
- `governance.py` (Tier 6, 55 endpoints) — `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE` + org scope (`actor_scope_org_pks`/`require_org_in_scope`); `/public/*`, `/elections/open-for-voting` and `/elections/{pk}/votes/self` need login only. `NSS_ERP_ADVISORY_BOARD_ADMIN` is auto-granted by `rbac_service.load_composite_grants()` (§63), not via `user_role`.
- `membership_change_request.py` (5 endpoints) — member-initiated Sakha Transfer / Apply for Darshak; source-release then destination-accept.
- `correspondence.py` (Tier 6, 19 endpoints) — `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE` + admin scope on `register_organization_pk` (`require_org_in_scope`/`actor_scope_org_pks`, same model as Foundation/Person/Membership). Also member-facing `my-applications`, `addressed-to-me`, `my-involvements` and a Sakha-President-then-Kendra `approval-steps/*` chain (`correspondence_approval_step`; `decide_approval_step()`). Status transitions follow the frozen §6.2 seven-row precondition table (business rules doc); reopening (ACTIONED/CLOSED → PENDING_ACTION) requires remarks (§6.3); responsible-party reassignment (§5.4) never itself transitions status. `/dispatch` (v1.1) and `/broadcast` (v1.1 follow-up) are the two exceptions to the admin-scope rule — they write counterpart rows into DIFFERENT organizations' registers than the one they check scope against, by design (see Open items).
- `attendance.py` (Tier 6, 20 endpoints, `/api/v1/attendance`) — Weekly Sangha Puja marking: `ATTENDANCE_MANAGE`/`ATTENDANCE_VIEW` + admin scope (Sakha admin or per-Sakha `NSS_ERP_ATTENDANCE_MARKER`). Attendance Review actions and exceptions are NOT permission-gated: `_require_review_authority()` checks the live Secretary/President seat on the member's home Sakha governing body (`NSS_ERP_ADMIN` overrides). Keyed on `sangha_sevi_pk`. Tests: `tests/api/test_attendance.py`, `tests/security/test_attendance_security.py`, shared fixtures `tests/attendance_support.py` (156 collected; written but NOT yet run against the DB — don't claim they pass); no Attendance UI test.
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
trailer to commits. Current state: `main` = `develop` = `v0.11.0` (Tier 5 released; old
`feature/*` branches are merged leftovers) — branch the next feature from `develop`.

## Open items

- `correspondence.py` two-sided org-to-org register (v1.1, owner-confirmed 2026-10-25): an OUTWARD
  row addressed to `recipient_type='ORGANIZATION'` can be dispatched (`POST /correspondence/{pk}/
  dispatch`, admin.html Dispatch button) to mint a linked, separately-numbered INWARD row in the
  recipient org's own register — `counterpart_correspondence_pk` (nullable self-FK) links the pair
  reciprocally. Scope is checked against the SENDER's `register_organization_pk` only; the
  recipient-side write is a system action, not re-checked against that org's own admin scope.
  PERSON/EXTERNAL recipients are untouched and stay single-row (no register of their own to write
  into). The DDL change was applied as a live `ALTER TABLE` against the existing dev DB (1751
  persons preserved) rather than a full rebuild — `02_build.sh`/`render_build.sh` are
  existence-gated and will pick up the DDL file's v1.1 column/constraints on any genuinely fresh
  build, so no further action is needed there. Tests: `tests/api/test_correspondence.py::
  TestDispatch`, `tests/ui/test_ui_admin_correspondence.py` (full admin-UI coverage, previously
  missing entirely despite the admin tab having existed for a while).
- `correspondence.py` broadcast/circular (v1.1 follow-up, owner-confirmed 2026-10-26, generalizing
  §4.7 ERP-FROZEN's own "Kendra circular to all Sakhas" example): `POST /correspondence/broadcast`
  (admin.html "Send as a circular" checkbox on the Send Application form, OUTWARD only) sends one
  circular to EVERY active descendant organization of a chosen type under the sender's org —
  `recipient_organization_type_code` + `org_subtree_pks()`. Still N real OUTWARD rows under the
  hood (§4.6's one-recipient-per-row CHECK is unconditional, so there is no "one row, many
  recipients" representation), each immediately dispatched via the SAME `_mint_inward_counterpart()`
  helper `dispatch_correspondence()` uses (extracted 2026-10-26 so the two endpoints share the
  mint+link logic instead of duplicating it) — one admin action instead of N manual create+dispatch
  repeats. Sender is always `ORGANIZATION` = the register org (no person/external override, unlike
  the single-letter create). The circular checkbox is gated (admin.js `corrCanBroadcast`, owner
  2026-10-26 "inside kendra sangha, anchalaika/zilla tab only") to a selected register org of type
  KENDRA/ANCHALIKA_SANGHA/ZILLA_SANGHA — never a Sakha or Patha Chakra register — and its "Send To
  Every" type dropdown is `corrBroadcastTypeOptions`: the DESCENDANT org types actually present in
  the selected org's live subtree (same parent/child links `org_subtree_pks()` walks), always
  excluding NILACHALA_KUTIRA/SMRUTI_MANDIRA — not the full `orgTypes` catalog. The ORGANIZATION
  recipient picker is likewise restricted to the register org's own descendants
  (`corrRecipientOrgCandidates` + `corrOnRecipientOrgQueryInput`, in-memory over
  `this.organizations`, NOT the global `corrSearchOrg`) — owner 2026-10-26 "in receipient only
  childrem under that parent should show". Both share one traversal, `_corrDescendantOrgs()`
  (`scopeOrgPkSet`'s own older walk is deliberately separate — many roots, roots included, returns
  pks, no type exclusion). The one upward exception (owner 2026-10-26 follow-up, resolving the
  previous open question: "Sakha, pathachakra, anachalik/zilla can send letter to kendra"):
  `corrRecipientOrgCandidates` additionally offers the real Kendra org as a recipient when the
  register org's type is SAKHA_SANGHA/PATHA_CHAKRA/ANCHALIKA_SANGHA/ZILLA_SANGHA — a Kendra
  register itself stays descendants-only (nothing further upward to address). The circular
  checkbox/dropdown render AFTER the Register Organization picker in the markup now (owner
  2026-10-26: "I want send circular under kendra and anchalika/zilla tab not above it.."), not
  before it — same `corrCanBroadcast` gate, just moved so it visibly belongs to the chosen register.
  The register-org switcher (`corrResolveDefaultOrg()`) resolves the admin's own
  `currentUser.scopes` org-type-agnostically (no role_code/org-type branching — covers a dual
  Anchalika+Zilla or any other admin); candidates are then grouped into one tab per org TIER via
  `CORR_REGISTER_TAB_GROUPS` (Kendra · **Anchalika/Zilla merged** · Patha Chakra · Sakha · Mahila
  Sangha), with a dropdown inside the active tier to pick WHICH org — never one tab per org (owner
  2026-10-26 "when tab is anchalika, we should have a dropdown to selcet the anchalika, not a tab
  for each anchalika, and it should be Anchalika/Zilla"). Because a tier costs one tab regardless of
  size, an NSS-wide/Kendra-equivalent admin (`isGovNssWideAdmin`) is now offered EVERY register org
  including all 175 Sakhas, not just the apex ones. A tier holding one org auto-selects it; a tier
  holding several opens on "Select organization…" (`createCorrespondence()` already 422s client-side
  on a missing register). §63's composite-grant rules (`_COMPOSITE_GRANT_RULES_SQL`) already map all
  five governing-body types (Kendra/Anchalika/Zilla/Patha Chakra/Sakha) to their respective admin
  roles. Tests:
  `tests/api/test_correspondence.py::TestBroadcast` (own isolated fresh-org fixture, not the real
  173-Sakha Kendra), `tests/ui/test_ui_admin_correspondence.py`.
- `correspondence.py` auto-dispatch + reply threading (v1.2 follow-up, owner-confirmed 2026-10-26).
  **Auto-dispatch:** "when the letter is sent intra org (within nss), i dont think there is any
  need to register it through receive application, it should auto register." `create_correspondence()`
  now attempts the exact same `_mint_inward_counterpart()` mint `dispatch_correspondence()` uses,
  immediately after inserting an eligible OUTWARD/`recipient_type=ORGANIZATION` row (recipient !=
  the register org) — collapsing the previous two-step "create, then separately click Dispatch"
  flow into one. Best-effort only: wrapped in `try/except HTTPException`, so a recipient with no
  `short_code` yet (the one realistic failure mode) leaves the row un-dispatched exactly as before
  this change, rather than failing the create. `POST /{pk}/dispatch` is unchanged in behavior but
  now primarily the MANUAL RETRY path for that one failure mode (and for pre-2026-10-26 rows, which
  never got an auto-dispatch attempt) — calling it after a successful auto-dispatch 409s, same as
  calling it twice always has. **Reply:** "we should also add reply option to letter too. which
  will have its own numbers (conceptually same process)" — `in_reply_to_correspondence_pk`
  (nullable self-FK, v1.2, many-to-one/no unique index — a letter may draw several replies) threads
  a reply to the letter it answers. Deliberately NOT a distinct numbering scheme: a reply is an
  ordinary `POST /correspondence` row (own `reference_number` via the normal per-register/
  per-direction/per-FY counter) that additionally carries this link — admin-supplied at create time,
  one-directional (the original row is never updated to point back; unlike
  `counterpart_correspondence_pk`, which IS reciprocal/system-minted by dispatch). admin.html's
  "Reply" button (detail view, `replyToCorrespondence()`) opens the ordinary create form prefilled:
  direction flips, subject gets a `Re: ` prefix, register org = the original's, and the "other
  party" carries over via the shared `corrPrefillParty()` helper — whichever party was NOT "us" in
  the original stays NOT "us" here, just occupying the opposite form field (sender vs recipient)
  because direction flipped. No reverse "replies to this" listing yet (would be a query, not a
  stored field — not built). Reply was launched from the detail view with a real bug (owner report,
  2026-10-26: "REPLY TO CORRESPONDENCE LETTER NOT WORKING. nothing happening"): the create form
  shares a markup wrapper (`x-show="!corrSelected && !corrDetailLoading"`) with the list view, so
  setting `corrCreateForm.show = true` from the detail view (where `corrSelected` is still set)
  opened the form INVISIBLY behind the still-showing detail panel — `replyToCorrespondence()` now
  also clears `corrSelected`, same as `backToCorrList()` does. Hard-rebuilt 2026-10-26 (the DB
  blocker that used to be documented here is resolved); full suite green. Tests:
  `tests/api/test_correspondence.py::TestDispatch` (rewritten for the new auto-dispatch semantics;
  one test exercises the short_code-missing retry path end-to-end), `TestReply` (new),
  `tests/ui/test_ui_admin_correspondence.py` (62→64 passed, including the detail-view-visibility
  regression test).
- `correspondence.py` event-driven lifecycle (v1.2 follow-up, owner-confirmed 2026-10-26, option 3
  of a 3-option proposal — "i wnat the transitionStatus to chnge automatically"). Amends §5.4/§6.2
  (ERP-FROZEN; see the `> **Amendment (2026-10-26...)**` blockquotes in
  `08_correspondence_register_business_rules.md` for the full rationale) — two transitions are now
  ALSO reachable automatically, as a side effect of a different action, alongside the pre-existing
  manual `/transition` path (additive, not a replacement):
  - **REGISTERED → PENDING_ACTION** fires in `assign_responsible_party()` the moment a responsible
    person/organization is actually SET (not cleared) on a REGISTERED record — populating either
    field is §6.2's entire precondition for this transition, so "reassignment does not
    automatically trigger a state transition" (§5.4) no longer holds for this ONE case. Every other
    state is unaffected: reassigning at PENDING_ACTION/ACTIONED/CLOSED still has no status side
    effect, same as before. One concrete consequence worth knowing: the old assign-then-manually-
    transition two-step collapses into one — calling `/transition` to PENDING_ACTION right after
    assigning now 422s "already PENDING_ACTION" (`tests/api/test_correspondence.py::TestTransition::
    test_pending_action_transition_is_now_redundant_after_auto_advance`), and clearing a responsible
    party on an already-auto-advanced record does NOT revert the status (§6.2's table has no
    PENDING_ACTION → REGISTERED transition at all).
  - **REGISTERED/PENDING_ACTION → ACTIONED** fires in `create_correspondence()` on the ORIGINAL
    letter the moment a reply naming it (`in_reply_to_correspondence_pk`) is created UNDER THE SAME
    REGISTER the original belongs to — sending a reply IS the action. Guarded narrowly: an
    already-ACTIONED original is a silent no-op; a CLOSED original is deliberately never
    auto-reopened (CLOSED → ACTIONED was never valid, manual or automatic); and the register-match
    guard is a real privilege-escalation guard, not a nicety — `require_org_in_scope()` only ever
    checks the REPLY's own register, so without this match a reply could otherwise mutate an
    out-of-scope record's status just by naming its pk (mutation-tested: removing the guard makes
    `test_reply_under_a_different_register_does_not_auto_action_the_original` fail).
  ACTIONED → CLOSED and both reopen transitions (§6.3) remain exclusively manual, deliberately —
  "matter complete" and "why reopened" both need an explicit human assertion no event here can
  stand in for. Tests: `tests/api/test_correspondence.py::TestEventDrivenLifecycle` (new, 8 tests)
  plus 2 pre-existing `TestTransition`/`TestResponsibleParty` tests updated for the new behavior.
- There is deliberately no `/forgot-password` page (the flow is inline on `/login`); forgot-password
  OTPs are never delivered (`api/routers/auth.py` TODO) — only visible via `otp_debug`.
- `/children-stats` and `/stats` recursive CTEs have no depth cap (`/hierarchy` caps at 10).
- `/person/{pk}/membership-summary`, `/register/lookup-existing` and `/register/claim` have no test coverage.
- `claim_approval.py::approve_claim()`, `admin.py::create_user()` and `admin.py::create_sangha_sevi()`
  each `INSERT INTO nss.sangha_sevi` independently — no shared helper. (`admin.py::update_status()`
  no longer provisions one; it 422s on activation when the person has no active `sangha_sevi`.)
- Pass 2 audit-actor FKs (`*_by_sangha_sevi_pk`) are still unconstrained on all tables.
- Deferred to later tiers: mobile/email verification, Organization contact-format CHECKs,
  inactive-person search, i18n, Kumari/Kishor/Sevak (Tier 9), Mahila (Tier 10).
- `PERSON_VIEW_SENSITIVE` is seeded but unwired; Aadhaar masking is unconditional.
