# tests/

Structured test suite for the NSS ERP application. Tests are organised into
four categories under separate subdirectories.

**Run status (2026-10-31):** this tree was re-counted by `pytest --collect-only` only. Nothing below
was executed in the session that refreshed these docs, and every file marked **NOT yet run** (all
Attendance suites and everything written 2026-10-30/31: person-address, Sakha re-parent, org
singleton, null-org scope, Sakha Asana parity, SAVEPOINT isolation, CORS-configured, Mahila/Advisory
Board security, and the new UI source-parsing files) has **never been run against a DB** — do not
treat them as passing until a run confirms it.

## Directory Structure

Per-file figures are `(N test functions; M collected)` — see the counting note below the tree.

```
tests/
├── conftest.py          # Shared fixtures: DB connection, SAVEPOINT rollback, TestClient, authed/anon clients
├── attendance_support.py     # Shared builders for the Attendance modules (not a test file; imports builders from tests/api/test_correspondence.py)
├── change_request_support.py # Shared builders for test_membership_change_request*.py (not a test file)
├── forgot_password_support.py # Shared builders for the forgot-password tests (not a test file)
├── registration_support.py   # Shared builders for the registration tests (not a test file)
├── reparent_support.py       # Shared builders for the Sakha re-parent tests (fresh Anchalika/Sakha via the admin API, Kendra/GB/Anchalika seat helpers, patch/decide shortcuts; builds on test_correspondence.py/attendance_support.py helpers; not a test file)
├── README.md            # This file
│
├── api/                 # API integration tests (FastAPI TestClient, no browser) — 31 files
│   ├── test_admin.py              # Tier 5 — admin CRUD, roles (incl. Assign-Role self-assign guard), orgs (87; 119)
│   ├── test_admin_credentials.py  # Tier 6 — member credential list/timeline/issue/promote (16; 16)
│   ├── test_admin_scope.py        # ADMIN-BR-076/077 admin-scope subtree enforcement across admin/claim endpoints (85; 99)
│   ├── test_attendance.py         # Tier 6 — Attendance API: pujas, bulk marking, corrections, exceptions, review trigger/workflow, stats (109; 155). NOT yet run
│   ├── test_audit.py              # Tier 5 — field-change-log viewer (13; 23)
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
│   ├── test_person.py             # Tier 3 — person list, detail, search (55; 74)
│   ├── test_person_address.py     # Person address POST/PATCH/DELETE: self-service + PERSON_MANAGE-in-scope, ADDRESS_TYPE validation, APPROVED-or-own-PENDING geography, single-primary invariant, soft delete (25; 25). NOT yet run
│   ├── test_registration.py       # Tier 5 — self-registration, claim approval, /register/address-types (63; 79)
│   ├── test_sakha_asana_parity.py # Sakha Asana == Sakha: stray-'SAKHA_SANGHA'-literal scan, SAKHA_LIKE_ORG_TYPES cross-layer consistency, behavioural parity (37; 48). NOT yet run
│   ├── test_sakha_branches.py     # Tier 2 — 175 Sakha branch seed data (33; 33)
│   ├── test_savepoint_isolation.py # tests/conftest.py SAVEPOINT architecture itself (11; 11). NOT yet run
│   └── test_sorting.py            # Shared column-sort-whitelist helper (14; 27)
│
├── db/                  # Database integrity tests (direct SQL via write_conn) — 6 files
│   ├── test_correspondence_schema.py # Tier 6 — Correspondence Register table invariants (32; 76)
│   ├── test_credential_schema.py  # Credential-table schema invariants — document_number uniqueness, one-active-per-member, validity CHECK, counter uniqueness (6; 13)
│   ├── test_data_integrity.py     # Cross-module entity smoke tests (23; 23)
│   ├── test_festival_schema.py    # festival_master / festival_calendar_date schema + resolver helpers (14; 20)
│   ├── test_organization_schema.py # ORG-BR-099 premises-address trigger (9; 40). NOT yet run
│   └── test_organization_singleton.py # trg_enforce_organization_singleton: KENDRA/NILACHALA_KUTIRA/SMRUTI_MANDIRA/ADVISORY_BOARD + central Mahila Sangha (7; 13). NOT yet run
│
├── security/            # Cross-tier security assertions — 16 files
│   ├── test_admin_security.py         # Admin endpoint auth/RBAC gating (17; 17)
│   ├── test_admin_surface_security.py # Admin-surface 401/403 matrix, parametrized over endpoints (7; 97)
│   ├── test_attendance_security.py    # Attendance auth/permission/admin-scope gating (parametrized over every endpoint) + review authority is a body seat (19; 83). NOT yet run
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
    ├── test_ui_attendance.py        # Attendance register UI (admin.html / org dashboard; attendance-register.js) (58; 132). NOT yet run
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

**Current totals** (re-counted 2026-10-31): **3718 collected items** (`pytest --collect-only -qq`) —
`tests/api/` 2111 (31 files), `tests/db/` 185 (6 files), `tests/security/` 836 (16 files),
`tests/ui/` 586 (31 test files). Integration (api + db + security) = 3132; UI = 586. AST count of
`def test_*` functions: 2548 (api 1730, db 91, security 309, ui 418). Not executed in the refresh
session; the 2026-10-30/31 additions and all Attendance suites have never been run against a DB.
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
made. `_reset_rate_limiter` (autouse, function-scoped) resets `api.main.limiter`'s in-memory
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

## Related docs

- `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` — Tier 1 API contract
- `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` — Tier 2 API contract
- `docs/03_Solution/api/PERSON_API_CONTRACT.md` — Tier 3 API contract
