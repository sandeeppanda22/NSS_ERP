# tests/

Structured test suite for the NSS ERP application. Tests are organised into
four categories under separate subdirectories.

**Run status (2026-11-05):** the owner's last full DB run (Python 3.15, after a rebuild) was 2 failed (fixed since,
unconfirmed), ~4336 passed, 47 skipped, so the backend suites (api/db/security) have now run against a real DB; the
playwright/browser checks of the newest UI (Assets & Property, Aadhaar, live refresh, audit diagnostics, the x-show fix) have not.
The "NOT yet run" markers below predate that run and are historical for the backend suites. Always invoke `python3 -m pytest`
(not bare `pytest`, which can resolve to an old interpreter launcher). Originally, every file marked **NOT yet run** (the three
Assets & Property suites (`test_assets_property*.py` + `test_asset_custodian_parity.py`, 757 items, written 2026-11-02/03), all
Attendance suites and everything written 2026-10-30/31: person-address, Sakha re-parent, org
singleton, null-org scope, Sakha Asana parity, SAVEPOINT isolation, CORS-configured, Mahila/Advisory
Board security, and the new UI source-parsing files) has **never been run against a DB** — do not
treat them as passing until a run confirms it.

## Directory Structure

Per-file figures are `(N test functions; M collected)` — see the counting note below the tree.

```
tests/
├── conftest.py          # Shared fixtures: DB connection, SAVEPOINT rollback, TestClient, authed/anon clients
├── aadhaar_support.py        # Shared fixtures for the Aadhaar modules (GDR-011; not a test file): random AES keys on `settings`, cast of NSS_ERP_ADMIN / scoped KENDRA_ADMIN in+out of scope / SAKHA_ADMIN / AUDITOR / subject member, `set_number()`/`db_row()` helpers
├── attendance_support.py     # Shared builders for the Attendance modules (not a test file; imports builders from tests/api/test_correspondence.py)
├── assets_property_support.py # Shared fixtures/builders for the Assets & Property modules (not a test file; builds on attendance_support.py: viewer_user/viewer_h (NSS_ERP_AUDITOR scoped to a Sakha), document_pks, make_property/make_asset/transition)
├── change_request_support.py # Shared builders for test_membership_change_request*.py (not a test file)
├── forgot_password_support.py # Shared builders for the forgot-password tests (not a test file)
├── registration_support.py   # Shared builders for the registration tests (not a test file)
├── reparent_support.py       # Shared builders for the Sakha re-parent tests (fresh Anchalika/Sakha via the admin API, Kendra/GB/Anchalika seat helpers, patch/decide shortcuts; builds on test_correspondence.py/attendance_support.py helpers; not a test file)
├── README.md            # This file
│
├── api/                 # API integration tests (FastAPI TestClient, no browser) — 36 files
│   ├── test_admin.py              # Tier 5 — admin CRUD, roles (incl. Assign-Role self-assign guard), orgs (87; 119)
│   ├── test_admin_credentials.py  # Tier 6 — member credential list/timeline/issue/promote (16; 16)
│   ├── test_legacy_local_number.py    # GDR-009 legacy-vs-new Local Sakha Number: validator, admin create matrix, attendance helper, registration_claim columns/patch (52; 26 run without a DB). NOT yet run against a DB
│   ├── test_patra_numbering.py        # GDR-009 §2A/§2B: Parichaya/Anumati Patra number — strict `<seq>/<yyyy>/<yyyy+1>` validator, legacy-vs-new resolver, allocator skipping taken numbers (stub-cursor: run without a DB), `issue_credential_at_enrolment()` Associate vs Darshaka, legacy vs new matrix (every member is minted a credential), Darshaka-cannot-attend check (48; 36 run without a DB). NOT yet run against a DB
│   ├── test_local_sakha_id.py     # Local Sakha ID always generated: allocator, shared creator, admin paths (14). NOT yet run
│   ├── test_admin_scope.py        # ADMIN-BR-076/077 admin-scope subtree enforcement across admin/claim endpoints (85; 99)
│   ├── test_assets_property.py    # Module #22 Assets & Property API: register/list/filters/PATCH/archive for properties and assets, SOL-AP-003 lifecycle + terminal states, custodianship assign/transfer/history (AP-017/018/042), property-only statutory records, maintenance, document links, scope + audit (90; 167; incl. custodian-must-be-physical on create/assign/transfer, every eligible type accepted, `include_sub_organizations` + scope intersection, Anchalika admin view-only, `TestBelongsTo`: set/clear/filter, inactive org 422, no scope widening, custodian rule unaffected). NOT yet run
│   ├── test_attendance.py         # Tier 6 — Attendance API: pujas, bulk marking, corrections, exceptions, review trigger/workflow, stats, live endpoint + concurrent-marking conflicts (126; 172). NOT yet run
│   ├── test_audit.py              # Tier 5 — field-change-log viewer (13; 23)
│   ├── test_audit_events.py       # Audit diagnostics: /audit/events (+facets, detail) and /audit/live-change-markers — DB-free route/permission/source checks + integration filter/sort/paging/cap behaviour (27; 27). NOT yet run against a DB
│   ├── test_auth.py               # Tier 5 — login, refresh, logout, change-password, sessions (39; 43)
│   ├── test_bootstrap.py          # Tier 0 — health, roles, permissions (14; 14)
│   ├── test_claim_approval.py     # Tier 5 — claim detail/edit/scope enforcement (36; 45)
│   ├── test_core_read_gaps.py     # organization selectable/wings/wing members, membership directory/darshak-summary, person search-selectable (43; 61). NOT yet run
│   ├── test_correspondence.py     # Tier 6 — Correspondence Register: register/list/detail/documents/finance refs, org scope, dispatch/broadcast/reply/event-driven lifecycle (182; 250)
│   ├── test_error_messages.py     # Human-readable validation/integrity-error messages (15; 20)
│   ├── test_family.py             # Tier 4 — family list, detail, members (52; 52)
│   ├── test_family_ownership.py   # Tier 5 — role-less-JWT ownership path: graph, add/remove, admin assign/revoke, transfer-head, FAM-036 majority (100; 104). New classes NOT yet run
│   ├── test_forgot_password.py    # Tier 5 — forgot/reset password (6; 6)
│   ├── test_foundation.py         # Tier 1 — master data, config, geographic, propose endpoints (52; 52)
│   ├── test_foundation_writes.py  # Foundation POST/PATCH (master-data, settings, sequences, festival calendar), propose endpoints, post-offices/sakha-postal-codes/festivals reads (64; 87). NOT yet run
│   ├── test_geo_approval.py       # Tier 5 — member-proposed geography review queue: list/detail/approve/correct, scope (28; 71)
│   ├── test_governance.py         # Tier 6 — bodies, assignments, elections, votes, results, Sakha scoping (248; 249)
│   ├── test_membership.py         # Tier 4 — membership list, search, affiliations (94; 117)
│   ├── test_membership_change_request.py # Tier 6 — Sakha Transfer / Apply for Darshak workflow (59; 76)
│   ├── test_null_org_scope.py     # KENDRA_MAHILA_SANGHA / ADVISORY_BOARD scope resolution + seeded footprints of both roles (18; 20). NOT yet run
│   ├── test_org_reparent.py       # Tier 6 — Sakha re-parent approval: direct-vs-request matrix, Sakha Asana, 4-step chain + fallback/collapse, live-seat-only authority, reject/cancel/supersede, apply + re-validation (60; 60). NOT yet run
│   ├── test_org_singleton.py      # API singleton rules (KENDRA/NILACHALA_KUTIRA/SMRUTI_MANDIRA/ADVISORY_BOARD create 422; central Mahila Sangha create/re-parent 422; local Mahila unrestricted) (5; 8). NOT yet run
│   ├── test_organization.py       # Tier 2 — org types, hierarchy, children, children-stats, stats (67; 67)
│   ├── test_aadhaar_service.py    # GDR-011 crypto/validation unit tests (43; DB-free — `pytest --noconftest tests/api/test_aadhaar_service.py`; the 11 AES-GCM items skip without the `cryptography` package)
│   ├── test_aadhaar.py            # GDR-011 capture (admin PATCH/create, 422/409/503, clear), last-4 gating matrix, reveal endpoint (200/403/404/401/500, audit row without value, rate limit), audit-trigger redaction (never run against a DB; needs `cryptography`)
│   ├── test_person.py             # Tier 3 — person list, detail, search (55; 74)
│   ├── test_person_address.py     # Person address POST/PATCH/DELETE: self-service + PERSON_MANAGE-in-scope, ADDRESS_TYPE validation, APPROVED-or-own-PENDING geography, single-primary invariant, soft delete (25; 25). NOT yet run
│   ├── test_registration.py       # Tier 5 — self-registration, claim approval, /register/address-types (63; 79)
│   ├── test_asset_custodian_parity.py # Assets & Property custodian rule (GDR-010 §2C): Python ASSET_CUSTODIAN_ORG_TYPES = SQL fn_is_asset_custodian_org_type body list = JS NSS.ASSET_CUSTODIAN_ORG_TYPES, build/validate wiring, 2026-11-02 owner-decision patch wiring (revoke / belongs-to, DB-free), live function + every ORGANIZATION_TYPE classified (22; 56). NOT yet run
│   ├── test_sakha_asana_parity.py # Sakha Asana == Sakha: stray-'SAKHA_SANGHA'-literal scan, SAKHA_LIKE_ORG_TYPES cross-layer consistency, behavioural parity (37; 48). NOT yet run
│   ├── test_sangha_sevi_insert_parity.py # no `INSERT INTO nss.sangha_sevi` under api/ outside helpers.py (the one shared creator); DB-free (3). Ran with --noconftest
│   ├── test_sakha_branches.py     # Tier 2 — 175 Sakha branch seed data (33; 33)
│   ├── test_live_changes.py       # live-refresh feed GET /live/changes: whitelist, JS<->Python table-map parity, SQL trigger list<->whitelist parity (TestSqlParity), per-user limit (DB-free), column-scoped `user_account` entry parity (ignored login-churn columns; login UPDATEs in auth.py touch only them), auth/shape/whitelist/change-number/churn integration (33; 49). Integration items NOT yet run
│   ├── test_rate_limit_per_user.py # per-user rate limit key + /live and /live/changes route limits (13; DB-free logic, 13 passed with --noconftest)
│   ├── test_savepoint_isolation.py # tests/conftest.py SAVEPOINT architecture itself (11; 11). NOT yet run
│   └── test_sorting.py            # Shared column-sort-whitelist helper (14; 27)
│
├── db/                  # Database integrity tests (direct SQL via write_conn) — 9 files
│   ├── test_assets_property_schema.py # Module #22 — constraint/index/trigger presence, no financial columns, property-only statutory records, reference-data/permission seed, XOR + one-ACTIVE-custodian + history-preservation + lifecycle guards (43; 150; incl. `fn_is_asset_custodian_org_type()` and the custodian-eligibility trigger on INSERT/UPDATE, the post-2026-11-02 grant set, withdrawn grants never active, `belongs_to_organization_pk` column + FK). NOT yet run
│   ├── test_correspondence_schema.py # Tier 6 — Correspondence Register table invariants (32; 76)
│   ├── test_credential_schema.py  # Credential-table schema invariants — document_number uniqueness, one-active-per-member, validity CHECK, counter uniqueness (6; 13)
│   ├── test_data_integrity.py     # Cross-module entity smoke tests (23; 23)
│   ├── test_festival_schema.py    # festival_master / festival_calendar_date schema + resolver helpers (14; 20)
│   ├── test_organization_schema.py # ORG-BR-099 premises-address trigger (9; 40). NOT yet run
│   ├── test_home_affiliation_guard.py # deferred home-affiliation guard + fn_next_sakha_local_number (14). NOT yet run
│   ├── test_organization_singleton.py # trg_enforce_organization_singleton: KENDRA/NILACHALA_KUTIRA/SMRUTI_MANDIRA/ADVISORY_BOARD + central Mahila Sangha (7; 13). NOT yet run
│   └── test_live_change_marker.py # live_change_marker + trg_live_change_marker: one bump per statement, rollback, SECURITY DEFINER, backend read, not audited, column-scoped `user_account` trigger (login bookkeeping does not bump; status/password/delete/insert do) (20; 20). NOT yet run against the project DB (the SQL itself ran once in a throwaway PostgreSQL 18 single-user instance)
│
├── security/            # Cross-tier security assertions — 17 files
│   ├── test_assets_property_security.py # Assets & Property: 401/403 matrix over all 34 (kind-expanded) route rows incl. Attendance Marker / Advisory Board admin / view-only role, custodian-scope refusals with exact messages, custodian-less records NSS-wide only, transfer needs both scopes (24; 292; incl. `include_sub_organizations` never widens scope, Mahila admin has no access, Anchalika/Zilla admins cannot write). NOT yet run
│   ├── test_admin_security.py         # Admin endpoint auth/RBAC gating (17; 17)
│   ├── test_admin_surface_security.py # Admin-surface 401/403 matrix, parametrized over endpoints (7; 97)
│   ├── test_audit_diagnostics_security.py # audit diagnostics endpoints: 401/403 on all four, no write verbs, not exposed under /foundation or /live, SQL metacharacters inert (40; 40). NOT yet run against a DB
│   ├── test_aadhaar_security.py       # GDR-011 source/OpenAPI sweeps (DB-free: no model carries ciphertext/hash, full number only in requests + PersonAadhaarResponse, last-4 only in the two gated responses) + response sweep and PERSON_VIEW_SENSITIVE footprint (DB; never run)
│   ├── test_live_security.py          # live-refresh feed gating: anonymous 401, login-only, no ids/non-whitelisted tables disclosed (14; 14). NOT yet run
│   ├── test_attendance_security.py    # Attendance auth/permission/admin-scope gating (parametrized over every endpoint) + review authority is a body seat (22; 89). NOT yet run
│   ├── test_audit_security.py         # Audit endpoint auth/RBAC gating (4; 4)
│   ├── test_auth_security.py          # Auth endpoint auth gating (4; 3)
│   ├── test_core_modules_security.py  # 401/403 matrix over foundation/organization/person/membership/family endpoints + self-or-permission (23; 168). NOT yet run
│   ├── test_correspondence_security.py # Correspondence auth/RBAC/org-scope gating (43; 96)
│   ├── test_cors_configured.py        # CORS with configured origins (fresh-subprocess imports of api.main) (11; 16). NOT yet run
│   ├── test_forgot_password_security.py # Forgot-password rate-limit/anti-enumeration (6; 6)
│   ├── test_governance_security.py    # Governance auth/RBAC/org-scope gating (58; 215)
│   ├── test_mahila_advisory_board_admin_security.py # Mahila admin reach/refusals; Advisory Board admin body-type rule (29; 36). NOT yet run
│   ├── test_membership_change_request_security.py # Membership-change-request gating (26; 30)
│   ├── test_organization_stats_security.py # /organizations/{pk}/stats and /wings scope enforcement, ADMIN-BR-076 (7; 10)
│   ├── test_person_address_security.py # Person address writes: 401 anon, 403 other member, PERSON_MANAGE scope in/out (10; 10). NOT yet run
│   ├── test_registration_security.py  # Registration endpoint gating incl. public surface (11; 11)
│   └── test_security_headers.py       # Headers, CSP, rate limiting, CORS, DEBUG_MODE (34; 34)
│
└── ui/                  # Browser UI tests (Playwright + Chromium, headless) — 31 files. Several are
    │                    # source-parsing tests that need no browser/server (marked "source-level")
    ├── conftest.py              # Browser/page fixtures (page, admin_page, member_page), login helpers, session-owned server (_ui_server)
    ├── register_support.py      # Shared register-form helpers (not a test file)
    ├── _csp_probe.py            # Throwaway script (not collected) — loads pages in Chromium and reports CSP violations/console errors; run by hand
    │
    │   ── Numbered files run sequentially (DB state cascades) ──
    ├── test_ui_06_register_submit.py # Registration: membership claim, address, full submission (9; 9)
    ├── test_ui_07_admin_write.py    # Admin: claim approve, status change, role assign, password (11; 11)
    │
    │   ── Unnumbered files (independent, any order) ──
    ├── test_ui_admin_claims.py      # Registration claims tabs, detail view (6; 6)
    ├── test_ui_admin_correspondence.py # Admin Correspondence tab: register switcher, send/dispatch/broadcast/reply, detail view (50; 70)
    ├── test_ui_admin_create_user.py # Create user account, reactivation (3; 3)
    ├── test_ui_legacy_local_number.py # source-level (GDR-009): register legacy question (+ Patra number inside the Yes branch, attendance hidden for a Darshaka) + admin Create User/Sangha Sevi checkbox/Patra input + Registration Approvals flag display/edit + dashboard Apply-for-Darshak hidden for PROBATIONARY (22; all run without a browser)
    ├── test_ui_admin_dropdown_resets.py # source-level: child dropdowns reset on parent change, PIN narrowed by district, stale-response guards (12; 16). NOT yet run
    ├── test_ui_admin_member_directory.py # Member Directory tab, search, detail panel (4; 4)
    ├── test_ui_admin_modals.py      # Admin write-path modals and confirm dialogs (4; 4)
    ├── test_ui_admin_orgs.py        # Organizations tab, table (3; 3)
    ├── test_ui_admin_persons.py     # Create person form, mandatory fields (8; 8)
    ├── test_ui_admin_roles.py       # Role assignment modal, dropdowns (6; 6)
    ├── test_ui_admin_status.py      # Status change modal (ACTIVE/LOCKED/INACTIVE) (5; 5)
    ├── test_ui_admin_tabs.py        # Admin sidebar tab switching / activeTab panels (2; 9)
    ├── test_ui_admin_users.py       # User list, search, filters, detail, INACTIVE styling (11; 11)
    ├── test_ui_advisory_board_dashboard.py # source-level: Advisory Board dashboard tab wiring (3; 3). NOT yet run
    ├── test_ui_assets_property.py   # source-level: Assets & Property admin UI (sidebar/panel/init-guard gating, write buttons only for ASSET_MANAGE, endpoint URLs, lifecycle tables mirror the router, labels/badges, stale-response guards, markup/JS parity) (60; 72; incl. custodian pickers restricted to physical organizations, hint, include-sub-organizations checkbox, "belongs to" picker/filter/body fields). NOT yet run under pytest
    ├── test_ui_audit_diagnostics.py # source-level Audit & Diagnostics tabs (nav, canViewAudit gating, endpoints, poll policy, no inline handlers) + node-run changedMarkers/relativeTime (18; 18; no browser)
    ├── test_ui_live_refresh.py      # source-level live-refresh wiring/policy + node-run pure logic (pollDelay, changedTabs) plus batch-2 wiring (every batch-2 tab mapped + reload hook + busy hook, silent loaders with stale-response guards, every whitelisted table mapped by a page) (45; 45; no browser)
    ├── test_ui_xshow_display.py     # source-level: no inline `display:` on any `x-show` element (Alpine removes it on show; use a flex/grid class) (1; 1)
    ├── test_ui_attendance.py        # Attendance register UI (admin.html / org dashboard; attendance-register.js) (68; 142). NOT yet run
    ├── test_ui_auth_refresh.py      # auth.js NSSAuth.apiFetch refresh/401-retry logic, fetch stubbed (18; 24)
    ├── test_ui_badges.py            # Shared badge system (badges.css) source-level checks (7; 13)
    ├── test_ui_dashboard.py         # Dashboard: all tabs, content rendering, edit profile, admin tabs, family state, documents, logout (62; 62)
    ├── test_ui_dashboard_address.py # source-level: member address editor (add/edit/remove/primary) with nssCombobox + NSSLocation (11; 22). NOT yet run
    ├── test_ui_family_management.py # dashboard.html Family tab management (3; 6)
    ├── test_ui_forgot_password.py   # Forgot/reset password flow (5; 5)
    ├── test_ui_governance_card.py   # Governance card on the dashboard (5; 10)
    ├── test_ui_location_cascade.py  # nss-location.js country/state/district/PIN cascade and resets (14; 16)
    ├── test_ui_login.py             # Login form, validation, force-password-change, redirect (8; 8)
    ├── test_ui_org_dashboard.py     # Org Dashboard tab (org-dashboard.js), six layouts + Advisory Board (22; 44)
    ├── test_ui_org_reparent.py      # source-level: Assign Sakha 202 handling/request panel (admin.js/html), President approvals panel (dashboard.js/html), shared chain helpers in nss-config.js (13; 13). NOT yet run
    ├── test_ui_register.py          # Registration 3-step navigation, field validation (9; 9)
    ├── test_ui_scoped_role_tabs.py  # source-level: ADMIN_TAB_MAP/guard for the Mahila + Advisory Board admin roles (13; 13). NOT yet run
    ├── test_ui_shared_datepicker.py # Shared nssDatePicker: no hand-written markup left, injection on every callsite, calendar, validation (22; 29)
    └── test_ui_topbar.py            # nss-layout.js role-badge collapsing + topbar layout rules (11; 12)
```

**Current totals** (re-counted 2026-11-05 with `python3 -m pytest --collect-only -qq`): **5173 collected items** —
`tests/api/` 2757 (43 files), `tests/db/` 401 (10 files), `tests/security/` 1227 (20 files),
`tests/ui/` 788 (37 files; incl. `test_ui_aadhaar.py` 14: Aadhaar capture/reveal UI source parsing + node-run parity of `NSS.aadhaar` with `api/services/aadhaar_service.py`, DB-free with `--noconftest`; and `test_ui_xshow_display.py` 1: no `x-show` element in `login/register/admin/dashboard.html` may carry `display:` in its inline style). Integration (api + db + security) = 4385; UI = 788. The Assets & Property backend files (`test_assets_property*.py` + `test_asset_custodian_parity.py`) account for 757 of the backend items; `tests/ui/test_ui_assets_property.py` adds 83 (source parsing only). Earlier totals for reference: 5170 (2026-11-04), 5033, 4905 (2026-11-03). The backend suites ran against a real DB in the owner's last full run (see Run status above); the UI files parse source and the newest UI has not been opened in a browser.
There is no Playwright test file for the Governance admin tabs.

**AST count vs. what pytest actually collects:** the per-file "N test functions" figures are counts of
`def test_*` functions, which differs from pytest's collected-item count in two ways. (1) Fixtures
named `test_*` (e.g. `test_user` in `tests/api/test_auth.py` and `tests/security/test_auth_security.py`)
are over-counted by an AST scan. (2) `@pytest.mark.parametrize` expands one function into many items —
heavy in `test_governance_security.py`, `test_core_modules_security.py`, `test_admin_surface_security.py`,
`test_attendance_security.py`, `test_ui_attendance.py` and several others.
`pytest.ini` declares `integration`/`ui`/`db` markers only — `tests/security/` files use
`pytest.mark.integration`, same as `tests/api/`, so there's no separate `security` marker.

## `conftest.py` — fixture architecture

The root `conftest.py` holds a **single session-scoped write-pool connection** (`_db_conn`,
via `api/database.py::get_write_pool()`) for the entire pytest run, wraps each test *module*
in a PostgreSQL `SAVEPOINT` (`_module_savepoint`, autouse), and overrides both `get_connection` (from `api.database`)
and `get_write_connection` (from `api.dependencies.auth`, the auditing one every router uses) FastAPI dependencies to yield that same connection. At the end of
each module, `ROLLBACK TO SAVEPOINT` undoes every INSERT/UPDATE/DELETE the module's tests
made. `_reset_rate_limiter` (autouse, function-scoped) resets the shared `limiter` (`api/rate_limit.py`, re-exported by `api.main`)'s in-memory
storage before every test.

Further fixtures in the root `conftest.py` (session-scoped unless noted):

| Fixture | Purpose |
|---------|---------|
| `client` | Plain `TestClient(app)` (used as a context manager, so lifespan runs) — unauthenticated unless a module overrides it |
| `write_conn` (module-scoped) | The **same** shared connection the API uses, for direct `INSERT`/assertion SQL inside a test or fixture; everything rolls back with the module's SAVEPOINT |
| `admin_view_token` | Mints (once per session) a JWT for an existing active admin that holds all four of `FOUNDATION_VIEW`/`ORGANIZATION_VIEW`/`PERSON_VIEW`/`MEMBERSHIP_VIEW`, after resetting that account's password inside the transaction; `pytest.skip()`s if no such admin exists (e.g. admin not bootstrapped) |
| `authed_client` | `TestClient` that sends `admin_view_token` as a Bearer header — how the permission-gated Tier 1-4 read-endpoint tests authenticate |
| `anon_client` | Explicitly unauthenticated `TestClient`, for negative 401 tests in modules whose `client` was overridden to carry a token |

`authed_client`/`anon_client` are deliberately plain `TestClient(app)` instances (not `with`
blocks) so they never fire the app's lifespan shutdown, which would close the shared session
connection.

`tests/ui/conftest.py` is separate: it is **not** SAVEPOINT-wrapped (UI tests drive a real running
server), defines `page`/`admin_page`/`member_page` fixtures plus helpers (`wait_for_alpine`,
`wait_for_toast`, `get_table_rows`, `click_nav_item`), logs in as `SS1`/`Admin@123` against
a free local port when the session starts its own server (`NSS_UI_BASE_URL` points at an external one; `NSS_UI_NO_SERVER=1` uses `http://127.0.0.1:8001`), caches/restores login sessions across tests, and auto-applies the `ui` marker. `member_page` currently logs in as
the **same** `SS1` admin account (no separate member account is bootstrapped yet).

**Implication for anyone adding a test:** don't assume any row already exists — either create
what you need via `write_conn` inside a fixture, or `pytest.skip()` gracefully.

## Locating date fields in UI tests

Every date field in the app is the **shared** `nssDatePicker`
(`frontend/assets/js/nss-datepicker.js`). Its markup is *not* written in the HTML pages — the
page only declares `x-data="nssDatePicker('<model.path>', {...})"` plus a `<label>`, and
`nssDatePickerExpand()` injects the identical input + popup into every callsite on
`DOMContentLoaded` (recursing into `<template>` content, since 9 of the 10 callsites are nested
inside `x-if`/`x-for` templates).

So **never locate a date field by `[x-model="form.some_date"]`** — no such element exists. Use
the stable hook the injector stamps on the picker root:

```python
PICKER = '[data-nss-dp="form.date_of_birth"]'      # root, one per callsite
INPUT  = f'{PICKER} input[x-model="display"]'      # visible DD/MM/YYYY input
```

The input holds the display value (`DD/MM/YYYY`); the model path holds ISO `YYYY-MM-DD`.
Because most pickers sit inside templates, Playwright sees them only after you navigate to the
tab / toggle the form that renders them — unlike a DOM walk, which also sees template content.

## Running

```bash
# ── All tests (API + DB + security + UI) ──────────────
pytest

# ── By category ───────────────────────────────────────
pytest tests/api/              # API integration tests only
pytest tests/db/               # database integrity tests only
pytest tests/security/         # cross-tier security assertions only
pytest tests/ui/               # UI browser tests only

# ── By marker ─────────────────────────────────────────
pytest -m integration          # tests/api/ + tests/db/ + tests/security/ (all carry this marker)
pytest -m db                   # database tests
pytest -m ui                   # UI tests

# ── Individual files ──────────────────────────────────
pytest tests/api/test_auth.py           # Tier 5 auth only
pytest tests/ui/test_ui_login.py        # Login UI only

# ── UI tests with visible browser ────────────────────
pytest tests/ui/ --headed               # watch the browser
pytest tests/ui/ --headed --slowmo 500  # slow down for debugging

# ── Single test ───────────────────────────────────────
pytest tests/api/test_bootstrap.py::TestHealth::test_health_returns_ok
```

## Prerequisites

### API & DB tests
- Local PostgreSQL running with nss schema bootstrapped
- `api/.env` configured with DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT,
  DB_WRITE_USER, DB_WRITE_PASSWORD, JWT_SECRET_KEY
- `pytest`, `httpx` and `httpx2` installed (Starlette's TestClient prefers `httpx2`; both pinned in `requirements.txt`)

### UI tests (additional)
- Server: started automatically by the session; log in `ui_test_server.log` (`_ui_server` in `tests/ui/conftest.py`: free port, live reload off, relaxed rate limit, stopped at the end). Use `NSS_UI_BASE_URL=...` to test a server you run yourself, or `NSS_UI_NO_SERVER=1` for the old `http://127.0.0.1:8001` behaviour.
- Playwright + Chromium installed:
  ```bash
  pip install pytest-playwright
  playwright install chromium
  ```
- Test admin account (SS1) bootstrapped via `scripts/bootstrap_admin.py`
- **Note:** SS1 logs in directly with `Admin@123` — `force_password_change = FALSE`,
  no change-password interstitial. The bootstrap seed is INSERT-only (`WHERE NOT
  EXISTS` guards), so if the account's local password ever drifts, rebuild the DB
  (the seed is designed for from-scratch rebuilds, not in-place resets).
- **Note:** UI tests run against the live database — they are NOT wrapped in
  SAVEPOINT rollback; every write a test drives through the real UI is a real,
  permanent commit. `tests/ui/conftest.py::_cleanup_ui_test_data` (session-scoped,
  autouse) hard-deletes the rows this leaves behind once the whole UI session
  finishes, by finding every `nss.person` row with an `@example.com` email (the
  marker `test_ui_06_register_submit.py`/`test_ui_07_admin_write.py` tag every
  test person with) and walking its dependents down to `person` itself, in FK
  order (no table in this schema has `ON DELETE CASCADE`). The deletes need the
  schema owner: set `DB_OWNER_USER=nss_db_owner` and `DB_OWNER_PASSWORD=...` in
  `api/.env` (`nss_db_writer` has no DELETE privilege); without them cleanup is
  skipped with a warning. Any **new** UI test
  that writes through a different table chain (e.g. a future Darshak-attendance
  or governance UI test) must extend `_SANGHA_SEVI_DEPENDENT_TABLES` /
  `_USER_ACCOUNT_DEPENDENT_TABLES` there, or use the same `@example.com` marker
  on data it alone is responsible for cleaning up — the fixture only knows about
  the tables the current register→approve flow populates.

- **Audit-actor FKs (2026-11-04):** every `*_by_sangha_sevi_pk` column has an FK to `sangha_sevi`
  (build Phase 13c), so fixtures must write a real `sangha_sevi_pk` or NULL as an actor, never a fake
  uuid; `tests/db/test_audit_actor_fk.py` guards it and `tests/ui/conftest.py::_purge_ui_test_rows`
  NULLs actor references to throwaway members before deleting them. `tests/api/test_recursive_cte_guard.py`
  fails on any `WITH RECURSIVE` in `api/` without the shared depth cap (never run against a DB).

## Related docs

- `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` — Tier 1 API contract
- `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` — Tier 2 API contract
- `docs/03_Solution/api/PERSON_API_CONTRACT.md` — Tier 3 API contract
