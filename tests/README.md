# tests/

Structured test suite for the NSS ERP application. Tests are organised into
four categories under separate subdirectories.

## Directory Structure

```
tests/
├── conftest.py          # Shared fixtures: DB connection, SAVEPOINT rollback, TestClient, authed/anon clients
├── README.md            # This file
│
├── api/                 # API integration tests (FastAPI TestClient, no browser)
│   ├── test_admin.py         # Tier 5 — admin CRUD, roles, orgs (78 tests)
│   ├── test_admin_credentials.py # Tier 6 — member credential list/timeline/issue/promote (16 tests)
│   ├── test_audit.py         # Tier 5 — field-change-log viewer (4 tests)
│   ├── test_auth.py          # Tier 5 — login, refresh, logout, change-password, sessions (23 tests)
│   ├── test_bootstrap.py     # Tier 0 — health, roles, permissions (9 tests)
│   ├── test_claim_approval.py # Tier 5 — claim detail/edit/scope enforcement (13 tests)
│   ├── test_correspondence.py # Tier 6 — Correspondence Register API: register/list/detail/documents/finance refs, org scope (26 tests)
│   ├── test_error_messages.py # Human-readable validation/integrity-error messages (15 tests)
│   ├── test_family.py        # Tier 4 — family list, detail, members (52 tests)
│   ├── test_family_ownership.py # Tier 5 — role-less-JWT ownership path: graph, add/remove
│   │                          #   member, admin assign/revoke, transfer-head (20 tests)
│   ├── test_forgot_password.py  # Tier 5 — forgot/reset password (6 tests)
│   ├── test_foundation.py    # Tier 1 — master data, config, geographic, propose endpoints (52 tests)
│   ├── test_geo_approval.py  # Tier 5 — member-proposed geography review queue: list/detail/approve/correct, scope (15 tests)
│   ├── test_governance.py    # Tier 6 — bodies, assignments, elections, votes, results, Sakha scoping (65 tests)
│   ├── test_membership_change_request.py # Tier 6 — Sakha Transfer / Apply for Darshak workflow (28 tests)
│   ├── test_membership.py    # Tier 4 — membership list, search, affiliations (94 tests)
│   ├── test_organization.py  # Tier 2 — org types, hierarchy, children, children-stats, stats (67 tests)
│   ├── test_person.py        # Tier 3 — person list, detail, search (55 tests)
│   ├── test_registration.py  # Tier 5 — self-registration, claim approval (17 tests)
│   ├── test_sakha_branches.py # Tier 2 — 175 Sakha branch seed data (33 tests)
│   └── test_sorting.py       # Shared column-sort-whitelist helper (14 tests)
│
├── db/                  # Database integrity tests (direct SQL via write_conn)
│   ├── test_correspondence_schema.py # Tier 6 — Correspondence Register table invariants (14 tests)
│   ├── test_credential_schema.py # Credential-table schema invariants — document_number
│   │                          #   uniqueness, one-active-per-member, validity CHECK,
│   │                          #   credential_sequence_counter uniqueness (6 tests)
│   ├── test_data_integrity.py  # Cross-module entity smoke tests (23 tests)
│   └── test_festival_schema.py # festival_master / festival_calendar_date schema + resolver helpers (14 tests)
│
├── security/            # Cross-tier security assertions (added after the api/db/ui split
│   │                     above; not a rename of anything)
│   ├── test_admin_security.py         # Admin endpoint auth/RBAC gating (17 tests)
│   ├── test_audit_security.py         # Audit endpoint auth/RBAC gating (4 tests)
│   ├── test_auth_security.py          # Auth endpoint auth gating (4 tests)
│   ├── test_correspondence_security.py # Correspondence endpoint auth/RBAC/org-scope gating (24 tests)
│   ├── test_forgot_password_security.py # Forgot-password rate-limit/anti-enumeration (6 tests)
│   ├── test_governance_security.py    # Governance endpoint auth/RBAC/org-scope gating (13 tests)
│   ├── test_membership_change_request_security.py # Membership-change-request gating (11 tests)
│   ├── test_organization_stats_security.py # /organizations/{pk}/stats scope enforcement, ADMIN-BR-076 (4 tests)
│   ├── test_registration_security.py  # Registration endpoint gating (3 tests)
│   └── test_security_headers.py       # Headers, CSP, rate limiting, CORS, DEBUG_MODE (24 tests)
│
└── ui/                  # Browser UI tests (Playwright + Chromium, headless)
    ├── conftest.py              # Browser/page fixtures (page, admin_page, member_page), login helpers
    ├── _csp_probe.py            # Throwaway script (not a test, not collected) — loads pages in
    │                            #   Chromium and reports CSP violations/console errors; run by hand
    │
    │   ── Numbered files run sequentially (DB state cascades) ──
    ├── test_ui_06_register_submit.py # Registration: membership claim, address, full submission (9 tests)
    ├── test_ui_07_admin_write.py    # Admin: claim approve, status change, role assign, password (11 tests)
    │
    │   ── Unnumbered files (independent, any order) ──
    ├── test_ui_login.py             # Login form, validation, force-password-change, redirect (8 tests)
    ├── test_ui_register.py          # Registration 3-step navigation, field validation (9 tests)
    ├── test_ui_dashboard.py         # Dashboard: all tabs, content rendering, edit profile,
    │                                #   admin tabs, family state, documents, logout (62 tests)
    ├── test_ui_forgot_password.py   # Forgot/reset password flow (5 tests)
    ├── test_ui_shared_datepicker.py # Shared nssDatePicker: no hand-written markup left in
    │                                #   any page, markup injection on every callsite, calendar
    │                                #   grid vs month/year, day selection, validation (22 tests)
    ├── test_ui_admin_users.py       # User list, search, filters, detail, INACTIVE styling (11 tests)
    ├── test_ui_admin_persons.py     # Create person form, mandatory fields (8 tests)
    ├── test_ui_admin_create_user.py # Create user account, reactivation (3 tests)
    ├── test_ui_admin_roles.py       # Role assignment modal, dropdowns (6 tests)
    ├── test_ui_admin_claims.py      # Registration claims tabs, detail view (6 tests)
    ├── test_ui_admin_status.py      # Status change modal (ACTIVE/LOCKED/INACTIVE) (5 tests)
    ├── test_ui_admin_orgs.py        # Organizations tab, table (3 tests)
    ├── test_ui_admin_member_directory.py # Member Directory tab, search, detail panel (4 tests)
    ├── test_ui_admin_modals.py      # Admin write-path modals and confirm dialogs (4 tests)
    ├── test_ui_admin_tabs.py        # Admin sidebar tab switching / activeTab panels (2 tests)
    ├── test_ui_auth_refresh.py      # auth.js NSSAuth.apiFetch refresh/401-retry logic, fetch stubbed (18 tests)
    ├── test_ui_location_cascade.py  # nss-location.js country/state/district/PIN cascade and resets (11 tests)
    ├── test_ui_topbar.py            # nss-layout.js role-badge collapsing + topbar layout rules (11 tests)
    ├── test_ui_badges.py            # Shared badge system (badges.css) source-level checks (7 tests)
    ├── test_ui_family_management.py # dashboard.html Family tab management (3 tests)
    └── test_ui_org_dashboard.py     # Org Dashboard tab (org-dashboard.js), six layouts (21 tests)
```

**Current grand total: 1118 tests** (AST-counted `test_*` functions, re-verified) — `tests/api/`
(702, across 21 files), `tests/db/` (57, across 4 files), `tests/security/` (110, across 10 files),
`tests/ui/` (249, across 23 test files — `conftest.py` and `_csp_probe.py` hold no tests). There is
no Playwright test for the governance or correspondence UI (neither page exists yet).

**AST count vs. what pytest actually collects** (`pytest --collect-only -q`, verified): the
per-file "(N tests)" figures in this README are counts of `def test_*` functions, which differs
from pytest's collected-item count in two ways. (1) Fixtures named `test_*` (e.g. `test_user` in
`tests/api/test_auth.py` and `tests/security/test_auth_security.py`, `test_org_pk` in
`tests/api/test_registration.py`) are over-counted by an AST scan. (2) `@pytest.mark.parametrize`
expands one function into many items — used in `test_admin.py`, `test_membership.py`,
`test_person.py`, `test_sorting.py`, `test_error_messages.py`, `test_credential_schema.py`,
`test_festival_schema.py` and several UI files. Collected-item totals (`pytest --collect-only -q`, re-run 2026-10-18; collection only, tests themselves not executed): `tests/api/` 810, `tests/db/` 98, `tests/security/` 109, `tests/ui/` 300 — **1317 items** for a bare `pytest`.
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
`http://127.0.0.1:8001` (override with `NSS_UI_BASE_URL`), caches/restores login sessions across tests, and auto-applies the `ui` marker. `member_page` currently logs in as
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
- `pytest` and `httpx` installed

### UI tests (additional)
- Local server running: `python3 -m uvicorn api.main:app --port 8001`
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
  order (no table in this schema has `ON DELETE CASCADE`). Any **new** UI test
  that writes through a different table chain (e.g. a future Darshak-attendance
  or governance UI test) must extend `_SANGHA_SEVI_DEPENDENT_TABLES` /
  `_USER_ACCOUNT_DEPENDENT_TABLES` there, or use the same `@example.com` marker
  on data it alone is responsible for cleaning up — the fixture only knows about
  the tables the current register→approve flow populates.

## Related docs

- `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` — Tier 1 API contract
- `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` — Tier 2 API contract
- `docs/03_Solution/api/PERSON_API_CONTRACT.md` — Tier 3 API contract
