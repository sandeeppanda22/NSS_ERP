# NSS ERP — Getting Started

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Getting Started |
| Repository Path | docs/03_Solution/architecture/GETTING_STARTED.md |
| Version | 2.0 (2026-11-01) |
| Status | Active |
| Authority | NSS ERP Architecture |

---

# 1. Prerequisites

- PostgreSQL 14+ (local or Neon.dev) with the extensions `pgcrypto`, `pg_trgm`, `btree_gin` and
  `postgis` available to `CREATE EXTENSION` (`01_extensions.sql` installs all four on a local
  database; install your OS's PostGIS package first). Nothing in `database/` or `api/` currently
  *uses* PostGIS, and Render/Neon (`render_build.sh`) skips it.
- Python **3.15** with pip (pinned in `.python-version` and `render.yaml`; owner decision 2026-11-03, no virtual environment — install into the system Python with `PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m pip install -r requirements.txt`, because Homebrew Pythons are PEP 668 "externally managed")
- psql CLI (included with PostgreSQL)
- Node.js + npm — pinned in `.nvmrc` (currently **26.12.1**; `nvm use`). **Optional** — only needed
  if you're changing Tailwind/DaisyUI CSS classes. `frontend/assets/css/tailwind.min.css` is a
  committed, generated artifact, so a fresh clone runs the app without Node.js installed at all.
- Playwright browsers — only for the UI test suite: `python3 -m playwright install chromium`
  (the `playwright` and `pytest-playwright` packages come with `requirements.txt`).

Clone and enter the repository; **every command in this guide is run from the repository root**:

```bash
git clone <repo-url> NSS_ERP && cd NSS_ERP
cp api/.env.example api/.env   # optional on macOS/Linux: step 2c generates a working api/.env for you
```

---

# 2. Database Setup

## macOS / Linux (bash)

```bash
# 2a. Create database and roles (as superuser)
psql -U postgres -d postgres -f database/scripts/00_create_database.sql

# 2b. Install extensions and create nss schema (as superuser)
psql -U postgres -d nss_erp -f database/scripts/01_extensions.sql

# 2c. Set role passwords + generate api/.env (prompts for each role's password)
./database/scripts/06_setup_env.sh
#     Re-run with --force to overwrite an existing api/.env:
#     ./database/scripts/06_setup_env.sh --force

# 2d. Build all DDL + seed (as nss_db_owner). Also runs `pip install -r requirements.txt`
#     (set PYTHON=/path/to/python3 if `python3` on PATH is not the interpreter you run the app with)
./database/scripts/02_build.sh

# 2e. Validate (as nss_db_owner) — [WARN] lines are informational; only [FAIL] means a problem
./database/scripts/03_validate.sh
```

What the build does that is new since Tier 6: it creates **86 tables** and, on *every* run, applies a
set of **idempotent patch files** (`run_sql`, not existence-gated — Advisory Board organization and
role-permission rows, the organization singleton trigger, the Sakha-like org-type function, the Local
Sakha ID allocator, the home-affiliation guard, the `registration_claim` legacy-member columns, the
attendance live-register index, the re-parent step CHECKs, the Sakha Asana governing-body shells, the Assets & Property guard triggers / custodian-eligibility function + trigger / `belongs_to_organization_pk` columns / reference data / `ASSET_*` permissions and the withdrawn-grant revocation, and — Finance, Tier 12 — the `FINANCE_*` permissions, the `PAYMENT_METHOD` master data (incl. UPI), the `FTX`/`RCT`/`PAY`/`FTR` id sequences and the initial Financial Year 2026-27).
The full list is in the header of `02_build.sh` and in `database/scripts/README.md`. Because the
patches run on every build, an **existing database does not need a rebuild for them — just re-run
`02_build.sh` and then `03_validate.sh`** (see Section 7a-2). The default admin login created in
Phase 13 is `SS1` / `Admin@123` (Section 4).

## Windows (PowerShell)

```powershell
# 2a. Create database and roles (as superuser)
psql -U postgres -d postgres -f database\scripts\00_create_database.sql

# 2b. Install extensions and create nss schema (as superuser)
psql -U postgres -d nss_erp -f database\scripts\01_extensions.sql

# 2c. Set role passwords + generate api\.env
#     Windows does not have 06_setup_env.sh — run the equivalent manually:
psql -U postgres -d postgres -c "ALTER ROLE nss_db_owner PASSWORD 'nssowner';"
psql -U postgres -d postgres -c "ALTER ROLE nss_db_backend PASSWORD 'nssadmin';"
psql -U postgres -d postgres -c "ALTER ROLE nss_db_writer PASSWORD 'nsswriter';"
#     Then create api\.env (see Section 3 below) or copy from a teammate.

# 2d. Build all DDL + seed (as nss_db_owner)
.\database\scripts\02_build.ps1

# 2e. Validate (as nss_db_owner)
.\database\scripts\03_validate.ps1
```

> The `.ps1` scripts mirror the `.sh` ones (build order and validate checks were diffed on
> 2026-11-01), but the 2026-10-30..11-01 changes to them have **never been run** — no Windows host
> has been available. If one misbehaves, compare with the `.sh` twin and report it.

> **Never commit real passwords.** The `.env` file is in `.gitignore`. Use `.pgpass` (macOS/Linux)
> or `%APPDATA%\postgresql\pgpass.conf` (Windows) for passwordless `psql` connections, or set
> `PGPASSWORD` in your shell session. `06_setup_env.sh` handles all of this for local dev.

---

# 3. API Setup

```bash
# Install Python dependencies
# macOS / Linux:
python3 -m pip install -r requirements.txt
# Windows:
#   py -m pip install -r requirements.txt
```

**`api/.env` is already generated** by Step 2c (`06_setup_env.sh`). It contains all
required variables: database credentials for both read and write pools, and a
randomly generated JWT secret. No manual editing needed for local dev. (To do it by hand,
`cp api/.env.example api/.env` and fill in `DB_NAME`, the three passwords and `JWT_SECRET_KEY`;
the file documents every optional variable — pool sizes, `RATE_LIMIT` (default `300/minute`),
CORS, CSP, `DEBUG_MODE`, `DEV_LIVE_RELOAD`. `DB_WRITE_USER`/`DB_WRITE_PASSWORD` and
`JWT_SECRET_KEY` are required for any login/write endpoint.)

If you're on **Windows** or need to create the file manually:

```powershell
@"
DB_NAME=nss_erp
DB_USER=nss_db_backend
DB_PASSWORD=nssadmin
DB_HOST=localhost
DB_PORT=5432
DB_WRITE_USER=nss_db_writer
DB_WRITE_PASSWORD=nsswriter
JWT_SECRET_KEY=replace_with_a_random_64char_hex_string
"@ | Out-File -Encoding utf8 api\.env
```

> **Generate a JWT secret** with `python3 -c "import secrets; print(secrets.token_hex(32))"` and
> paste the output as `JWT_SECRET_KEY`. Never reuse this across environments.

---

# 3b. Frontend CSS (optional — only if editing Tailwind/DaisyUI classes)

```bash
npm install
npm run css:build   # one-shot rebuild of frontend/assets/css/tailwind.min.css
npm run css:watch   # rebuild on every file change, for active frontend dev
```

Skip this section if you're not touching `frontend/*.html` or `frontend/assets/js/*.js` class
names — the built CSS is already committed. `render_build.sh` runs this build automatically on
every deploy.

---

# 4. Start the API

```bash
# macOS / Linux:
python3 -m uvicorn api.main:app --reload --port 8001

# Windows:
py -m uvicorn api.main:app --reload --port 8001
```

**URLs:**

| URL | What |
|-----|------|
| `http://localhost:8001/` | Redirects to `/login` |
| `http://localhost:8001/login` | Login (Authentication) |
| `http://localhost:8001/register` | Self-Registration |
| `http://localhost:8001/forgot-password` | **No such page, by design** — forgot/reset-password is inline on `/login`; `POST /api/v1/auth/forgot-password`/`reset-password` back it |
| `http://localhost:8001/dashboard` | Member Dashboard (post-login landing page) |
| `http://localhost:8001/admin` | Admin console (Users and Assign Role, Create User/Sangha-Sevi/Organization, Organizations, Assign Sakhas, Registration Approvals, Geo Approvals, Sakha re-parent approvals, Person/Member Directory, Organization Hierarchy, Org Dashboard incl. Advisory Board and Mahila views, Attendance register, Correspondence, Governance, Reference Data, Geography, System Settings) |
| `http://localhost:8001/docs` | Swagger UI (OpenAPI) |
| `http://localhost:8001/api/v1/` | API endpoints |

**Default login** (created by build Phase 13, `scripts/bootstrap_admin.py`): username `SS1` (or `P1`),
password `Admin@123`. The build never resets an existing admin's password. SS1 is the reserved
**system account** (`is_system_account = TRUE`, attached to the Kendra) and is deliberately exempt from
several member rules: the Sakha-only membership trigger (MBR-038A), the home-affiliation guard (it needs
no Local Sakha ID), the Parichaya/Anumati credential invariant, and the member-roster/attendance
counts. Change the password before using anything outside local dev.

The six standalone Tier 0-4 verification pages (`/bootstrap`, `/foundation`, `/organization`,
`/person`, `/family`, `/membership`) have been retired — their functionality now lives inside
`/admin` and `/dashboard` (see `frontend/README.md`). See `api/README.md` for the full
per-router endpoint list and security-middleware detail.

---

# 5. Run Tests

```bash
# macOS / Linux:
python3 -m pytest tests/ -v          # everything (UI tests need Playwright browsers)
python3 -m pytest -m integration     # tests/api + tests/db + tests/security
python3 -m pytest -m ui              # tests/ui only
python3 -m pytest tests/api/test_organization.py   # one file

# Windows:
py -m pytest tests/ -v
```

**5476 collected items** (`pytest --collect-only -qq`, 2026-11-10): `tests/api/` 2833 (39 files — router and
integration coverage), `tests/db/` 438 (10 files — cross-module data integrity, credential/festival schema,
organization singleton triggers, home-affiliation guard, live-refresh change marker), `tests/security/` 1385 (19 files — auth-gating,
401/403/RBAC, CSP/rate-limit/CORS) and `tests/ui/` 820 (36 files — Playwright browser tests plus
source-parsing tests). Re-run `--collect-only -qq` for current numbers; this count drifts every session.
See `tests/README.md` for the per-file inventory.

How the suite works:

- Every `tests/api|db|security` test is a **real integration test** (nothing mocked) against your local
  database; it needs a bootstrapped DB and `api/.env`. `tests/conftest.py` overrides both DB pools to yield one
  session-scoped writer connection, wraps each test **module** in a `SAVEPOINT` rolled back at teardown and
  adds a **per-test savepoint** so a DB error in one test cannot poison the transaction for the rest of the
  module. That is what lets the suite run on a seed-less DB and leave no rows behind.
- The UI suite **starts its own uvicorn server** on a free port (live reload off, rate limit relaxed) and stops
  it afterwards — do not run `uvicorn` yourself for it. To reuse a server you started, set
  `NSS_UI_BASE_URL=http://127.0.0.1:8001` (or `NSS_UI_NO_SERVER=1`).
- A few tests `pytest.skip()` against the seed-less DB (e.g. `test_kumari_transition_has_event`,
  `TestChildrenStats`) instead of failing.
- **Run status caveat.** Almost nothing written between 2026-10-30 and 2026-11-01 had run against a database
  until the owner's first full run on 2026-10-31, which produced failures that were fixed in commit
  `0d956eb`. Treat anything added after that run (the Local Sakha ID / legacy-number / Patra numbering suites,
  `test_home_affiliation_guard.py`, the validate additions, the `.ps1` changes) as unverified until you have
  run it yourself — and do not report a suite as passing without running it.

---

# 5b. Manual Smoke-Test Checklist (features added 2026-10-30 .. 2026-11-01)

Log in at `/login` as `SS1` / `Admin@123` unless stated. A fresh build has no members: create them through
`/register` plus **Registration Approvals**, or with Create User / Create Sangha-Sevi in `/admin`.

1. **Register page.** `/register`: the country → state → district → city/village cascade fills in order;
   choosing a district narrows the PIN list ("PIN by district"); the password fields have the shared eye toggle
   (`nss-password`); the "were you already a member?" Yes/No choice reveals the Local Sakha Number (and Patra
   number) fields for Yes and hides them for No (see item 9).
2. **Member address editor.** `/dashboard` → profile → edit address: change country/state/district/city/PIN,
   save, reload — the address persists; clearing a dependent dropdown resets the ones below it.
3. **Assign Role.** `/admin` → Users → select a user → Assign Role: pick role and (for scoped roles) an
   organization, save. Granting a role to **yourself** is refused (self-assign guard) unless you are a Kendra Administrator.
4. **Mahila / Advisory Board admins.** Assign `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` and
   `NSS_ERP_ADVISORY_BOARD_ADMIN` to two test users (no organization needed — they use NULL-organization
   scopes). Each should see only their own Mahila / Advisory Board tabs and nothing global.
5. **Advisory Board organization.** Organizations lists one `Advisory Board` (type `ADVISORY_BOARD`, code `ADB`,
   short code `NSSAB`, under the Kendra). Its Org Dashboard renders; its Correspondence register works. Trying to
   create a second one is rejected (singleton trigger).
6. **Sakha re-parent approval chain.** Org Hierarchy / Organizations → re-parent a Sakha to another
   Anchalika/Zilla. As a non-Kendra admin it opens a request with four steps: Sakha President → leaving
   Anchalika/Zilla President → destination Anchalika/Zilla President → Kendra President; each approver sees it
   in their queue. A Kendra Governing Body member or `NSS_ERP_ADMIN` re-parents directly (exempt from the chain).
7. **Live attendance register.** Make two users attendance markers for one Sakha (`NSS_ERP_ATTENDANCE_MARKER`).
   Open Mark Attendance in two browsers: a mark by one appears in the other within about 2 s (adaptive polling: slower when idle),
   shows who marked it, and a conflicting edit prompts before overwriting; the percentage on screen is
   roster-based. A Darshaka (probationary) member cannot be marked at another Sakha — they must transfer.
8. **Sakha Asana as a Sakha.** Create a `SAKHA_ASANA`: it gets a Sakha Governing Body shell, takes members,
   attendance, a Local Sakha ID and Sakha-level correspondence exactly like a Sakha Sangha.
9. **Legacy vs new numbering (GDR-009).** Register once as a *legacy* member supplying their existing Local
   Sakha Number and Parichaya/Anumati number, once as *new*. On approval the legacy member keeps the supplied
   numbers; the new member is auto-numbered (Local Sakha ID is always generated, and every active member must
   end up with a home affiliation). The claim form refuses a flag/number mismatch with a clear 422.
10. **Validate.** `./database/scripts/03_validate.sh` — expect no `[FAIL]`; `[WARN]` for members without a home
    affiliation/credential means pre-existing data the build deliberately does not backfill.

---


# 6. Script Reference

See `database/scripts/README.md` for detailed script reference (what each script does, build
phases, role naming conventions, cross-platform principles).

---

# 7. Database Rebuild (Clean Slate)

The build script (`02_build.sh` / `02_build.ps1`) is idempotent for re-runs. However, if you need
a **clean rebuild** — for example after schema changes, seed data edits, or switching branches —
you must drop and recreate the database. For the much more common case of just picking up a
**newly added table** with no other changes, see Section 7a-2 (Incremental Rebuild) below instead
— it needs no drop at all.

## Full Rebuild Procedure

### macOS / Linux (bash)

```bash
# 7a. Stop the API server (if running) and terminate stale connections
#     Stale psql sessions or uvicorn connection pools will block the drop.
psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nss_erp' AND pid <> pg_backend_pid();"

# 7b. Drop the existing database (as superuser)
#     WARNING: This destroys ALL data in nss_erp.
psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS nss_erp;"

# 7c. Recreate database and roles (idempotent — roles survive the drop)
psql -U postgres -d postgres -f database/scripts/00_create_database.sql

# 7d. Reinstall extensions and recreate nss schema
psql -U postgres -d nss_erp -f database/scripts/01_extensions.sql

# 7e. Set role passwords + regenerate api/.env
./database/scripts/06_setup_env.sh --force

# 7f. Full build (DDL + seed, all phases)
./database/scripts/02_build.sh

# 7g. Validate
./database/scripts/03_validate.sh
```

### Windows (PowerShell)

```powershell
# 7a. Stop the API server (if running) and terminate stale connections
#     Stale psql sessions or uvicorn connection pools will block the drop.
psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nss_erp' AND pid <> pg_backend_pid();"

# 7b. Drop the existing database (as superuser)
#     WARNING: This destroys ALL data in nss_erp.
psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS nss_erp;"

# 7c. Recreate database and roles (idempotent -- roles survive the drop)
psql -U postgres -d postgres -f database\scripts\00_create_database.sql

# 7d. Reinstall extensions and recreate nss schema
psql -U postgres -d nss_erp -f database\scripts\01_extensions.sql

# 7e. Set role passwords + create api\.env
#     Windows: run ALTER ROLE manually (see Section 2 Windows steps)
#     and create api\.env manually (see Section 3).

# 7f. Full build (DDL + seed, all phases)
.\database\scripts\02_build.ps1

# 7g. Validate
.\database\scripts\03_validate.ps1
```

## When to Rebuild

| Scenario | Action |
|---|---|
| DDL schema change (new column, altered constraint) on an existing table **with an idempotent patch file** (see the patch list in `02_build.sh`) | Re-run `02_build` — no rebuild |
| DDL schema change (new column, altered constraint) with no patch file | Full rebuild required |
| Seed data edit (new rows, changed values) on a pre-existing table with no patch file | Full rebuild required |
| **New table added to the build script, nothing else changed** | **Incremental rebuild (Section 7a-2) — no drop needed** |
| Branch switch with different schema state | Full rebuild required |
| API code change only (no DB changes) | No rebuild needed — restart uvicorn |
| New test added (no DB changes) | No rebuild needed |

---

# 7a-2. Incremental Rebuild (new tables and idempotent patches — existing data preserved)

As of **Version 3.0, 2026-10-05**, `02_build.sh` (and `render_build.sh` for Render deploys) use a
**deterministic, existence-gated bootstrap**: before touching any business table, the script asks
the Postgres catalog directly — `to_regclass('nss.<table>')` — whether that table already exists.

- Table **already exists** → its DDL *and* its seed are both skipped entirely. Nothing is read,
  written, dropped, or re-seeded. Your existing local rows are never touched.
- Table **absent** → the script creates it (runs its DDL), then runs its seed exactly once.

**Idempotent patch files (2026-10-30 .. 11-01).** Because the existence gate would otherwise strand
changes to existing tables, the build also runs a set of patch files on *every* run (`run_sql`, outside the
gate): `04_role_permission_mahila_advisory_board_patch.sql`, the organization singleton trigger,
`10_sakha_like_org_type_function.sql`, `07_advisory_board_organization_patch.sql`,
`19_sakha_local_number_allocator.sql`, `20_home_affiliation_guard.sql`,
`06_registration_claim_legacy_member_patch.sql`, `13_governance_nomination_refile_index.sql`,
`04_sakha_asana_governing_body_patch.sql`, `05_attendance_live_version_index_patch.sql`,
`09_organization_reparent_step_source_role_patch.sql` (full list: `02_build.sh` header). So **an existing
database from before these changes needs only `02_build.sh` + `03_validate.sh` re-run** — validate FAILs if a
patch's effect is missing. The home-affiliation guard and singleton trigger never scan existing rows, so a
database already holding members without a Local Sakha ID builds fine; `03_validate` then WARNs about them.
Nothing backfills those members (deliberate owner decision, see Section 8).

This means that when the **only** change is a new table being added to the project (e.g. a new
module's DDL/seed files wired into the build script), you do **not** need to drop the database at
all — just re-run the build directly against your existing local database.

## Full Incremental Rebuild Procedure

### macOS / Linux (bash)

```bash
# 7a-2a. Stop the API server (if running)
#        Not strictly required for a new-table-only rebuild (no DROP involved), but a running
#        uvicorn holding open connections can make the new table's GRANT step noisy — safest
#        to stop it first.

# 7a-2b. Re-run the build — as nss_db_owner. No drop, no --force, no re-entering passwords.
./database/scripts/02_build.sh

# 7a-2c. Validate
./database/scripts/03_validate.sh

# 7a-2d. Restart the API
python3 -m uvicorn api.main:app --reload --port 8001
```

### Windows (PowerShell)

```powershell
# 7a-2a. Stop the API server (if running)
#        Not strictly required for a new-table-only rebuild (no DROP involved), but a running
#        uvicorn holding open connections can make the new table's GRANT step noisy — safest
#        to stop it first.

# 7a-2b. Re-run the build — as nss_db_owner. No drop, no --force, no re-entering passwords.
.\database\scripts\02_build.ps1

# 7a-2c. Validate
.\database\scripts\03_validate.ps1

# 7a-2d. Restart the API
py -m uvicorn api.main:app --reload --port 8001
```

> **Windows parity note:** `02_build.ps1` now uses the same deterministic catalog-check model as
> `02_build.sh` — `Test-TableExists` calls `to_regclass('nss.<table>')` directly, and
> `Invoke-Ddl`/`Invoke-Seed` skip DDL+seed for any table already present. Both scripts behave
> identically for incremental rebuilds.

Read the build output for confirmation:

```
  [CHECK] user_session  (nss.user_session) ...
  [NEW]  user_session  (nss.user_session absent — creating)
  [OK]   user_session
  ...
  [CHECK] organization  (nss.organization) ...
  [EXISTS] organization  (nss.organization already present — DDL + seed skipped, local data preserved)
```

Every table you already had reports `[EXISTS]`; only the genuinely new one reports `[NEW]` and
actually runs DDL/seed.

**When incremental rebuild is NOT enough — fall back to the full rebuild in Section 7:**
- An **existing** table's DDL changed (column added/altered/dropped, constraint changed) — the
  existence check only sees "table is present," it does not diff columns.
- An **existing** table's seed data was edited (new/changed/removed rows) — seed is skipped
  wholesale for any pre-existing table, so edited seed rows never apply via incremental rebuild.
- A table was renamed or removed — the old table stays around; nothing in this model drops a table.
- **Concrete example (2026-10-09, §63 composite auto-grant rule):** `role_master`'s seed gained a
  10th row (`NSS_ERP_ADVISORY_BOARD_ADMIN`), `body_type_master`'s seed gained 3 rows
  (`ANCHALIKA_GOVERNING_BODY`, `ZILLA_GOVERNING_BODY`, `PATHA_CHAKRA_GOVERNING_BODY`), and
  `admin_scope`'s `chk_admin_scope_org_consistency` CHECK constraint was widened to also exempt
  `KENDRA`/`KENDRA_MAHILA_SANGHA`. On any environment where `role_master`/`body_type_master`/
  `admin_scope` already exist, a routine rebuild or Render redeploy will skip all three changes
  — only a full hard rebuild picks them up.
- **Concrete example (2026-10-21, DB-level governance seat-count backstop):** `body_type_master`
  gained a `max_members` column (`01_body_type_master.sql`, DDL in place + idempotent
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` safety net, same pattern as
  `master_data.applicable_modules` / `organization.has_own_premises`) and its seed
  (`seed/08_governance/01_body_type_master.sql`) gained an `UPDATE` setting it to 9 for
  `KENDRA_GOVERNING_BODY`/`SAKHA_GOVERNING_BODY` and 3 for `SEVAK_SANGHA_EXECUTIVE`/
  `ANCHALIKA_GOVERNING_BODY`/`ZILLA_GOVERNING_BODY`/`PATHA_CHAKRA_GOVERNING_BODY`. On any
  environment where `body_type_master` already exists, a routine rebuild or Render redeploy
  skips the column add and the `UPDATE` — only a full hard rebuild picks them up. The new
  trigger functions themselves (`12_governance_seat_limits.sql`) are not table-gated (`run_sql`,
  like `11_governance_immutability.sql`) and so are (re)applied on every build/redeploy
  regardless; they simply enforce nothing extra on an un-rebuilt environment because
  `max_members` reads `NULL`.
- **Concrete example (2026-10-21, Registration-Time Geography Creation):** `city_village`,
  `postal_code`, and `post_office` each gained a `submitted_by_person_pk` column (DDL in place +
  idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` safety net, same pattern as
  `master_data.applicable_modules` / `organization.has_own_premises`) plus a deferred FK to
  `nss.person` wired in `05_membership/16_foundation_audit_fk.sql` (Phase 7b). `district` is
  deliberately **not** touched — it is never auto-created at registration. On any environment
  where these three tables already exist, a routine rebuild or Render redeploy skips the column
  add entirely — **and this one is not a silent no-op**: `api/routers/registration.py::register()`
  always calls `resolve_or_create_city_village`/`resolve_or_create_postal_code`/
  `resolve_or_create_post_office` with `pending_submitter_person_pk` set, and the `INSERT` built
  when that argument is non-`None` names the column explicitly — so every self-registration that
  creates a genuinely new geo row 500s with `column "submitted_by_person_pk" does not exist`
  (mirrors the `election_type` case) until a full hard rebuild. The post-Phase-13 backfill step
  (see Build Phases below) tolerates the same missing-column condition itself (`[SKIP]`, not
  `[FAIL]`), so it never breaks the build/redeploy on its own — but the registration 500s above
  still require the hard rebuild to actually fix.

---

## Build Phases (execution order)

The build script executes in this order (**86 tables**). All phases run within a
single `02_build.sh` / `02_build.ps1` invocation; `render_build.sh` mirrors them for Render/Neon:

| Phase | Module | What |
|------:|--------|------|
| 0 | Bootstrap RBAC | 3 tables + seed (roles, permissions) + idempotent permission patches, incl. `08_finance_permissions_patch.sql` (`FINANCE_VIEW`/`FINANCE_MANAGE`/`FINANCE_APPROVE`, 14 PROPOSED grants) |
| 1 | Foundation DDL | 14 tables, incl. the 5-level geography chain (`country` → `state` → `district` → `city_village` → `postal_code`) and `festival_master`/`festival_calendar_date`; `system_event_log` (15th) is created separately in Phase 14 |
| 2 | Foundation Seed | Master categories, master data, geography, sequences, settings |
| 3 | Organization DDL | 1 table (includes short_code column, performance indexes) + address-restriction, Kumari/Sevak, **singleton** (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, ADVISORY_BOARD, central Mahila Sangha) triggers + `fn_is_sakha_like_org_type()` |
| 4 | Organization Seed | Base organizations, Sakha postal codes, 175 Sakha branches, then the Advisory Board patch (`ADVISORY_BOARD` org type + the singleton Advisory Board organization → 179 organizations) |
| 5 | Person DDL | 2 tables |
| 6 | Family DDL | 6 tables (includes performance indexes) + move-transition guard + `family_head_history` audit-column patch |
| 7 | Membership DDL | 16 tables (includes performance indexes) + Sakha-only trigger + Local Sakha ID allocator (`fn_next_sakha_local_number`) + home-affiliation guard (deferred constraint triggers) |
| 7b | Foundation audit FKs | `16_foundation_audit_fk.sql` — real `submitted_by_`/`reviewed_by_` FKs now that `sangha_sevi` exists |
| 8 | *(reserved — no demo data)* | |
| 9 | Grant Backend | Read-only access for `nss_db_backend` |
| 10 | Authentication DDL | 5 tables (`user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session`) + `registration_claim` legacy-member patch (`is_legacy_member`, `darshak_is_legacy_member`, agreement CHECKs) |
| 11 | Administration DDL | 2 tables (`user_role`, `admin_scope`) |
| 11b | Governance DDL | 10 tables (`body_type_master`, `position_master`, `body_master`, `body_member_assignment`, `acting_position_assignment`, `election`, `election_nomination`, `election_vote`, `election_result`, `election_vote_participation`) + ballot-immutability function/triggers (`11_governance_immutability.sql`) + seat-count-limit functions/triggers (`12_governance_seat_limits.sql`, 2026-10-21): a DB-level backstop behind the API's `_COMPOSITION_RULES` — `fn_enforce_body_seat_limit()` caps total active seats per body (from `body_type_master.max_members`, or 8/3 for `MAHILA_PARICHALANA_MANDALI` by `body_master.organization_pk`-nullness), and `fn_enforce_advisory_one_seat_per_sakha()` rejects a second Advisory Board nominee from an already-represented Sakha. Also adds `body_type_master.max_members` (`01_body_type_master.sql`, v1.1) — **existence-gated like the `election_type` case above: a routine rebuild/redeploy against an already-bootstrapped `body_type_master` will NOT add this column or its seeded values; only a full hard rebuild does.** Until then the seat-count triggers see `max_members IS NULL` for every type and the flat-cap check is a no-op (the Mahila/Advisory special cases are unaffected, since they don't depend on this column) |
| 11c | Governance Seed | `body_type_master` (8 types), `position_master` (10 positions), `body_master` (3 NSS-wide bodies: Kendra Governing Body, Advisory Board, central Mahila Parichalana Mandali — plus one empty Sakha Governing Body shell per active Sakha organization, 175 rows, no office-holders; members are assigned later via election/appointment), then the Sakha Asana governing-body patch (a shell per active `SAKHA_ASANA`) |
| 11d | Correspondence DDL | 5 tables (`correspondence`, `correspondence_document`, `correspondence_finance_reference`, `correspondence_sequence_counter`, `correspondence_approval_step`) |
| 11e | Attendance DDL | 4 tables (`weekly_sangha_puja`, `weekly_sangha_puja_attendance`, `attendance_exception`, `attendance_review`) + live-register index patch |
| 11f | Organization re-parent approval DDL | 2 tables (`organization_reparent_request`, `organization_reparent_step`) + step-role/step-order CHECK patch (Sakha President → leaving Anchalika/Zilla → destination Anchalika/Zilla → Kendra President) |
| 11g | Assets & Property DDL | 7 tables (`property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`) + idempotent guard triggers (`08_assets_property_guards.sql`) + idempotent custodian-must-be-physical function/trigger (`09_asset_custodian_org_type_function.sql`) + idempotent `10_assets_property_belongs_to_patch.sql` (nullable `belongs_to_organization_pk` + FK + index on `property`/`asset`, GDR-010 §2D) + idempotent `11_assets_property_acquisition_method_patch.sql` (nullable `acquisition_method_master_data_pk` + FK + index, GDR-010 §2E) + idempotent reference-data patch (`PROPERTY`/`ASSET` sequences, 7 master categories incl. `ACQUISITION_METHOD`, `DISPOSED`/`RETIRED` end reasons) + idempotent `12_assets_property_terminal_custody_patch.sql` (ENDs the ACTIVE custodianship of already DISPOSED/RETIRED records, GDR-010 §2F; after the reference data) and `trg_custodianship_terminal_guard` in `08_assets_property_guards.sql`; Phase 0 also runs the `ASSET_VIEW`/`ASSET_MANAGE` permissions patch (12 grants; Anchalika/Zilla view-only, Mahila none) and `06_assets_property_permissions_revoke_patch.sql` (soft-deletes the 4 grants the original 16-row patch created) (GDR-010) |
| 11h | Live refresh DDL | 1 table (`live_change_marker` + sequence `live_change_seq`) + idempotent statement-level change-marker triggers on the watched tables (`12_live_refresh/02_live_change_triggers.sql`, every build; invoked at the END of Phase 11i so the Finance tables exist first) |
| 11i | Finance DDL | 7 tables (`financial_year`, `financial_scope`, `fund_master`, `financial_transaction`, `financial_receipt`, `financial_payment`, `financial_transfer`; `ddl/14_finance/`) + idempotent reference-data patch (`seed/12_finance/01_finance_reference_data_patch.sql`: `PAYMENT_METHOD` master data incl. UPI, id sequences, initial Financial Year 2026-27). Runs after Phase 11h, so the live-refresh triggers file lists the Finance tables too |
| 12 | Grant Writer | `SELECT`/`INSERT`/`UPDATE` for `nss_db_writer` on every `nss` table |
| 13 | Admin Bootstrap | Seed NSSAdmin user account (runtime bootstrap via `bootstrap_admin.py`) |
| 13b | Geo Attribution Backfill | `UPDATE`s `city_village`/`postal_code`/`post_office.submitted_by_person_pk` to NSS Admin's person_pk (`P1`) for every row where it's still `NULL` and `submitted_by_sangha_sevi_pk` is also `NULL` (i.e. the bulk-reference-seeded rows from Phase 2, which had no app-level submitter) — attribution consistency, 2026-10-21. Must run after Phase 13 since `P1`'s `person_pk` doesn't exist before it (Phase 2's bulk geo seed runs 11 phases earlier). Idempotent (only touches `NULL` rows); tolerates a missing `submitted_by_person_pk` column (un-rebuilt environment) as `[SKIP]`, not `[FAIL]` |
| 14 | Audit DDL | `system_event_log` table + `fn_audit_trigger()` attached to every `nss.*` table |
| 15 | Demo Seed *(optional, local dev only)* | `database/seed/demo/nss_demo_seed.sql` (gitignored), run only when `RUN_DEMO_SEED` is truthy; not in `render_build.sh`. Includes demo office-holder assignments (`body_member_assignment`) onto the Phase 11c Sakha Governing Body shells, so local dev has populated governing bodies to test against |

## Troubleshooting

**"database nss_erp is being accessed by other users"**

Close all psql sessions and stop the API server before dropping:

```bash
# macOS / Linux:
psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nss_erp' AND pid <> pg_backend_pid();"
psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS nss_erp;"
```

```powershell
# Windows:
psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nss_erp' AND pid <> pg_backend_pid();"
psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS nss_erp;"
```

**Build fails mid-way**

The build aborts on the first real error (non-idempotent failures). Fix the
failing SQL file, then run a full rebuild from Step 7a — partial rebuilds on a
broken schema are not supported.

**`UniqueViolation` / "only one active … organization" when creating an organization**

The organization singleton trigger (`trg_enforce_organization_singleton`) allows one active row each for
`KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`, `ADVISORY_BOARD` and the central Mahila Sangha (a
`MAHILA_SANGHA` whose parent is the Kendra). Tests or scripts that create one of these must either use a
different type or soft-delete/rename the existing row inside their savepoint. The query in
`database/scripts/README.md` (Phase 3) shows what the live data holds.

**`value too long for type character varying(5)` creating an organization**

`organization.short_code` is `VARCHAR(5)`. Use short codes of at most five characters (the Advisory Board is
`NSSAB`); long generated test codes must be truncated.

**`InFailedSqlTransaction: current transaction is aborted` cascading through a test module**

One statement failed inside the shared test transaction and every later statement in it fails. Find the first
real error above the cascade. The per-test savepoint fixture normally contains this; if you provoke a DB error on
purpose inside a test, wrap it in the `isolated_savepoint` fixture.

**`NameError` on import / `python3 -c "import api.main"` fails**

A name was used without being imported (seen after moving shared logic into `api/helpers.py`). Run `python3 -c "import api.main"` after every edit — it catches missing imports before any
test does.

**HTTP 429 from the live attendance register**

The register polls `/attendance/pujas/{pk}/live` (2 s while active). That route has its own per-user limit
(`LIVE_ATTENDANCE_RATE_LIMIT`, default `120/minute`, counted per signed-in user), so markers on one WiFi no longer
share the per-IP budget. A 429 on it now means one account is polling more than ~120 times a minute (many tabs?).
The live-refresh feed `/live/changes` likewise has its own per-user limit (`LIVE_CHANGES_RATE_LIMIT`, `60/minute`). Other endpoints still use the global per-IP `RATE_LIMIT` (`300/minute`); raise it in `api/.env` for local
multi-user testing. Polling is adaptive (2 s active, 10 s after a quiet minute, paused in hidden tabs, back-off on errors).

**`[WARN]` in `03_validate`**

`[WARN]` (never `[FAIL]`) means row-count minimums not met, or pre-existing data the build does not repair:
members without a home affiliation / Local Sakha ID, members without an ACTIVE Parichaya/Anumati credential, or
claims whose legacy flag disagrees with the stored number. Diagnostic SELECTs are in
`database/scripts/README.md`.

---

# 8. Open Items and Pending Decisions

- **GDR-005 .. GDR-009 are `Approved`** (2026-11-01, on the project owner's instruction; `docs/00_Project_Governance/GDR/`): Advisory Board as a
  singleton organization (005), NULL-organization administrative scopes (006), Sakha re-parenting requires the
  President chain (007), Sakha Asana is a Sakha for all organizational purposes (008), legacy members supply
  their Local Sakha Number while all others are auto-numbered (009). The repo holds no separate NSS Governing Body
  minutes; add their reference to each record if they exist. The code already implements them.
- **Live refresh (2026-11-03):** pages refresh themselves from one `GET /api/v1/live/changes` poll per open page (per-user `LIVE_CHANGES_RATE_LIMIT`, default `60/minute`; table-level, no data, driven by the `live_change_marker` table that the build creates and triggers keep current; 5 s active / 15 s idle; a busy form/modal gets a "new updates - Refresh" banner instead of a reload). Nothing needed from the developer; if a page shows HTTP 429 from `/live/changes`, raise that variable in `api/.env`. Existing databases get triggers for newly watched tables (batch 2: Users, Organizations, directories, reference data, geography, settings, member dashboard) by re-running `12_live_refresh/02_live_change_triggers.sql` (build Phase 11h runs it every build). Not yet exercised against a DB or browser.
- **Live attendance register rate limiting is done:** the per-user limit (fix 1: `/live` is limited per signed-in
  user, `LIVE_ATTENDANCE_RATE_LIMIT`, default `120/minute`) and the adaptive poll cadence (fix 2) are both in place.
- **Advisory Board meetings and decisions** inside Programmes & Events are not specified yet.
- **No backfill of existing members lacking a home affiliation / Local Sakha ID** — deliberately not written
  (owner decision). `03_validate` WARNs and the diagnostic SELECT lists them.
- Forgot-password OTPs are never delivered (only visible via `otp_debug` with `DEBUG_MODE`); there is
  deliberately no `/forgot-password` page.
- The `.ps1` scripts' 2026-10-30..11-01 changes and every validate addition from that period have not been run
  against a database.
