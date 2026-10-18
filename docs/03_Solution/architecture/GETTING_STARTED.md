# NSS ERP — Getting Started

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Getting Started |
| Repository Path | docs/03_Solution/architecture/GETTING_STARTED.md |
| Version | 1.9 |
| Status | Active |
| Authority | NSS ERP Architecture |

---

# 1. Prerequisites

- PostgreSQL 14+ (local or Neon.dev)
- Python 3.12+ with pip
- psql CLI (included with PostgreSQL)
- Node.js + npm — **optional**, only needed if you're changing Tailwind/DaisyUI CSS classes.
  `frontend/assets/css/tailwind.min.css` is a committed, generated artifact, so a fresh clone
  runs the app without Node.js installed at all.

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

# 2d. Build all DDL + seed (as nss_db_owner)
./database/scripts/02_build.sh

# 2e. Validate (as nss_db_owner)
./database/scripts/03_validate.sh
```

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
randomly generated JWT secret. No manual editing needed for local dev.

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
| `http://localhost:8001/admin` | Admin console (Users, Create User/Sangha-Sevi/Organization, Organizations, Assign Sakhas, Registration Approvals, Geo Approvals, Person/Member Directory, Organization Hierarchy, Org Dashboard, Reference Data, Geography, System Settings) |
| `http://localhost:8001/docs` | Swagger UI (OpenAPI) |
| `http://localhost:8001/api/v1/` | API endpoints |

The six standalone Tier 0-4 verification pages (`/bootstrap`, `/foundation`, `/organization`,
`/person`, `/family`, `/membership`) have been retired — their functionality now lives inside
`/admin` and `/dashboard` (see `frontend/README.md`). See `api/README.md` for the full
per-router endpoint list and security-middleware detail.

---

# 5. Run Tests

```bash
# macOS / Linux:
python3 -m pytest tests/ -v

# Windows:
py -m pytest tests/ -v
```

**1118 test functions (1317 collected items, `pytest --collect-only`, 2026-10-18)**, split across four directories: 702 in `tests/api/` (21 files — routers +
integration coverage), 57 in `tests/db/` (cross-module data integrity, credential-schema and festival-schema
invariants), 110 in `tests/security/` (auth-gating/401/403/RBAC + CSP/rate-limit/CORS
assertions), and 249 in `tests/ui/` (23 Playwright browser-test files — needs Playwright
browsers installed and a running app).
`test_kumari_transition_has_event` and `TestChildrenStats` gracefully `pytest.skip()` against
the seed-less database rather than fail. See `tests/README.md` for the full per-file test
inventory.

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
| DDL schema change (new column, altered constraint) | Full rebuild required |
| Seed data edit (new rows, changed values) | Full rebuild required |
| **New table added to the build script, nothing else changed** | **Incremental rebuild (Section 7a-2) — no drop needed** |
| Branch switch with different schema state | Full rebuild required |
| API code change only (no DB changes) | No rebuild needed — restart uvicorn |
| New test added (no DB changes) | No rebuild needed |

---

# 7a-2. Incremental Rebuild (new table only — existing data preserved)

As of **Version 3.0, 2026-10-05**, `02_build.sh` (and `render_build.sh` for Render deploys) use a
**deterministic, existence-gated bootstrap**: before touching any business table, the script asks
the Postgres catalog directly — `to_regclass('nss.<table>')` — whether that table already exists.

- Table **already exists** → its DDL *and* its seed are both skipped entirely. Nothing is read,
  written, dropped, or re-seeded. Your existing local rows are never touched.
- Table **absent** → the script creates it (runs its DDL), then runs its seed exactly once.

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

> **Windows parity note:** `02_build.ps1` has **not yet** been ported to the catalog-check model —
> it still uses the older "skip on `already exists` error text" approach. The practical result for
> a new-table-only rebuild is the same (existing tables/rows are left alone, the new table gets
> created), but it is not the same deterministic mechanism as `02_build.sh`. Ask to have
> `02_build.ps1` ported if you need the two to match exactly.

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

---

## Build Phases (execution order)

The build script executes in this order. All phases run within a
single `02_build.sh` / `02_build.ps1` invocation:

| Phase | Module | What |
|------:|--------|------|
| 0 | Bootstrap RBAC | 3 tables + seed (roles, permissions) |
| 1 | Foundation DDL | 14 tables, incl. the 5-level geography chain (`country` → `state` → `district` → `city_village` → `postal_code`) and `festival_master`/`festival_calendar_date`; `system_event_log` (15th) is created separately in Phase 14 |
| 2 | Foundation Seed | Master categories, master data, geography, sequences, settings |
| 3 | Organization DDL | 1 table (includes short_code column, performance indexes) |
| 4 | Organization Seed | Base organizations, Sakha postal codes, 175 Sakha branches |
| 5 | Person DDL | 2 tables |
| 6 | Family DDL | 6 tables (includes performance indexes) |
| 7 | Membership DDL | 16 tables (includes performance indexes) |
| 8 | *(reserved — no demo data)* | |
| 9 | Grant Backend | Read-only access for `nss_db_backend` |
| 10 | Authentication DDL | 5 tables (`user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session`) |
| 11 | Administration DDL | 2 tables (`user_role`, `admin_scope`) |
| 11b | Governance DDL | 10 tables (`body_type_master`, `position_master`, `body_master`, `body_member_assignment`, `acting_position_assignment`, `election`, `election_nomination`, `election_vote`, `election_result`, `election_vote_participation`) + ballot-immutability function/triggers (`11_governance_immutability.sql`) |
| 11c | Governance Seed | `body_type_master` (8 types), `position_master` (10 positions), `body_master` (3 NSS-wide bodies: Kendra Governing Body, Advisory Board, central Mahila Parichalana Mandali — plus one empty Sakha Governing Body shell per active Sakha organization, 175 rows, no office-holders; members are assigned later via election/appointment) |
| 12 | Grant Writer | `SELECT`/`INSERT`/`UPDATE` for `nss_db_writer` on every `nss` table |
| 13 | Admin Bootstrap | Seed NSSAdmin user account (runtime bootstrap via `bootstrap_admin.py`) |
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
