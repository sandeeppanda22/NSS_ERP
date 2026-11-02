# NSS ERP — Database Code Explanations

| Field       | Value                                                                     |
|-------------|----------------------------------------------------------------------------|
| Document    | DATABASE_CODE_EXPLANATIONS                                               |
| Version     | 1.3                                                                       |
| Scope       | All SQL DDL, seed, and build/validate scripts under `database/`          |
| Status      | Complete for Tier 0-4 (updated: Tier 4 Family — `family_link` graph-edge table). **Not covered:** Tier 5 DDL/seed (`06_authentication/`, `07_administration/`, `system_event_log`/audit trigger, `family_admin`, `darshak_attendance_registration`, `credential_sequence_counter`, festival tables, `post_office` and the member-assisted-entry columns, `seed/04_admin/`, bulk geography seeds) — see the per-folder READMEs under `database/`. Also mentions `city_village_postal_code_map` and `01_person_master_tables.sql`, which no longer exist |

---

## 1. Purpose of this document

This is a file-by-file, line-by-line companion to every hand-written SQL/shell/PowerShell
artifact under `database/`. It exists at a different altitude than the documents it sits
alongside:

- `database/README.md` covers **execution order** (bootstrap sequence, phase table, module
  implementation status) and **what to run**, not what each statement inside a file does.
- `database/ddl/*/README.md` and `database/seed/*/README.md` are **per-folder summaries** —
  one paragraph per file, not column-by-column detail.
- This document is the **exhaustive walkthrough**: every column, every type, every constraint,
  every index, and — for seed files — the exact row count and representative data, for every
  file in `database/`.

Use `database/README.md` to know *when* to run a file and in what order. Use this document to
know *exactly what happens* when it runs.

**The build order, top to bottom — read this first if you're new to the codebase.** Every file
below is explained in exactly this sequence, because each phase's tables must exist before the
next phase's foreign keys can reference them:

```
database/scripts/00_create_database.sql   (superuser)  → creates nss_erp DB + the two
database/scripts/01_extensions.sql        (superuser)     PostgreSQL roles + the nss schema
                    │
                    ▼
database/scripts/02_build.sh / .ps1  (as nss_db_owner) — runs every DDL + seed file below,
                    │                                     in this exact order, via psql
                    ▼
   Bootstrap (Tier 0)         ddl/00_bootstrap/*.sql  →  seed/00_bootstrap/*.sql
   (3 tables)                 role_master, permission_master, role_permission
                    │
                    ▼
   Foundation (Tier 1)        ddl/01_foundation/*.sql →  seed/01_foundation/*.sql
   (12 tables)                master_category…city_village_postal_code_map
                    │
                    ▼
   Organization (Tier 2)      ddl/02_organization/*.sql → seed/02_organization/*.sql
   (1 table)                  organization (type/status now resolved via Foundation
                    │         master_data — see ORGANIZATION_TYPE / STATUS categories)
                    ▼
database/scripts/03_validate.sh / .ps1  (as nss_db_owner) — row-count/FK-integrity checks
database/scripts/04_grant_backend.sql   (as nss_db_owner) — grants nss_db_backend SELECT-only
                    │                                        access, needed before the API
                    ▼                                        can connect at all
The FastAPI app (see API_CODE_EXPLANATIONS.md) can now query nss.* through nss_db_backend

   Person (superseded prototype, ddl/03_person/ + seed/03_person/) — never run by
   02_build.sh; explained fully below anyway since it's still code in the repo, but
   every section for it says so.
```

Scope note: `database/ddl/03_person/` and `database/seed/03_person/` are a **superseded
prototype** — not executed by `database/scripts/02_build.sh`/`02_build.ps1`, kept only for
reference (see `database/ddl/03_person/README.md` and `database/README.md` → "Superseded
Artifacts"). They are still explained fully below because they are still code in the
repository, but every section for them opens with an explicit supersession notice.

Addendum (Tier 4 Family): `database/ddl/04_family/` (5 tables — `family_group`,
`family_relationship`, `family_head_history`, `family_transition_history`, `family_link`) and
`database/seed/04_family/` are **real, implemented DDL** — unlike the `03_person/` prototype
directly above, Family's tables are built against the current, real `nss.*` schema (schema-
qualified table names, `master_category`/`master_data`-driven classification, the real
`nss.person`/`nss.organization` FK targets) and are documented in that section, following all of
Foundation/Organization's real-DDL conventions rather than the superseded prototype's.

---

## 2. Files

### database/scripts/00_create_database.sql

**Requirement**

Run once, by a PostgreSQL **superuser**, against the `postgres` database. This is the very
first script in the bootstrap sequence — before it runs, neither the `nss_erp` database nor
the `nss_db_owner`/`nss_db_backend` roles exist, so nothing else in `database/` can execute.
Without this file: there is no database to connect to, no owner role to run DDL as, and no
backend role for the FastAPI app to authenticate as. It is intentionally idempotent (safe to
re-run) because it uses existence checks before every `CREATE`.

**Line-by-line explanation**

```sql
CREATE EXTENSION IF NOT EXISTS dblink;
```

Installs the `dblink` extension in the `postgres` database. This is required because `CREATE
DATABASE` cannot be executed inside a transaction block (and top-level `DO $$ ... $$` blocks are
implicitly transactional), so the script uses `dblink_exec` to open a *separate* connection back
to the server and issue `CREATE DATABASE` there, outside the enclosing block's transaction.

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'nss_db_owner'
    ) THEN
        CREATE ROLE nss_db_owner
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
        RAISE NOTICE 'Role nss_db_owner created (LOGIN, no password — set one before use).';
    ELSE
        ALTER ROLE nss_db_owner LOGIN;
        RAISE NOTICE 'Role nss_db_owner already exists — ensured LOGIN.';
    END IF;
END
$$;
```

`DO $$ ... $$` block #1 creates the `nss_db_owner` role. It checks `pg_catalog.pg_roles` for an
existing row with `rolname = 'nss_db_owner'`. If absent, `CREATE ROLE nss_db_owner LOGIN
NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;` creates a login role that is explicitly **not** a
superuser, cannot create databases or other roles, and does not automatically inherit privileges
of roles it might later be granted membership in. This is the DDL/schema-owning role (distinct
from the ERP application role `NSS_ERP_ADMIN`, which is a row in `role_master`, not a PostgreSQL
role — see the naming-convention comment block at the top of the file). If the role is already
present, `ALTER ROLE nss_db_owner LOGIN;` idempotently ensures LOGIN is set even if the role
pre-existed from an older script version. No password is set here — `RAISE NOTICE` reminds the
operator to set one via `ALTER ROLE ... PASSWORD '...'` afterward.

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'nss_db_backend'
    ) THEN
        CREATE ROLE nss_db_backend
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
        RAISE NOTICE 'Role nss_db_backend created (LOGIN, no password — set one before use).';
    ELSE
        ALTER ROLE nss_db_backend LOGIN;
        RAISE NOTICE 'Role nss_db_backend already exists — ensured LOGIN.';
    END IF;
END
$$;
```

`DO $$ ... $$` block #2 creates `nss_db_backend` with the identical existence-check /
`CREATE ROLE ... LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT` / `ALTER ROLE ... LOGIN`
pattern. This is the runtime role the FastAPI app connects as.

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'nss_erp'
    ) THEN
        PERFORM dblink_exec(
            'dbname=postgres host=localhost port=5432 user=postgres password=root',
            'CREATE DATABASE nss_erp OWNER nss_db_owner'
        );
        RAISE NOTICE 'Database nss_erp created.';
    ELSE
        RAISE NOTICE 'Database nss_erp already exists — skipping.';
    END IF;
END
$$;
```

`DO $$ ... $$` block #3 creates the `nss_erp` database. It checks `pg_database` for `datname =
'nss_erp'`. If absent, it calls `dblink_exec('dbname=postgres host=localhost port=5432
user=postgres password=root', 'CREATE DATABASE nss_erp OWNER nss_db_owner')`. The connection
string is hardcoded to `localhost:5432` with a **local-dev placeholder password `root`** for the
`postgres` superuser — `dblink` does not inherit the invoking session's authentication, so this
must be edited before running against any shared/non-local environment (called out explicitly in
both this file's header comment and `database/README.md`). If the database is already present,
it just `RAISE NOTICE`s and skips — idempotent.

```sql
GRANT CONNECT ON DATABASE nss_erp TO nss_db_backend;
```

The only privilege granted in this file; table-level grants happen later in
`04_grant_backend.sql`, after tables exist.

---

### database/scripts/01_extensions.sql

**Requirement**

Run once, by a PostgreSQL **superuser**, against the `nss_erp` database, immediately after
`00_create_database.sql`. Installs the PostgreSQL extensions the Foundation DDL depends on and
creates the `nss` schema that every table in the project lives in. Without this file:
`gen_random_uuid()` (used as the default for every `_pk` column in every table) does not exist,
none of the `gin_trgm_ops` trigram indexes used throughout Foundation/Organization DDL can be
created, and there is no `nss` schema for any `CREATE TABLE nss.*` statement to target.

**Line-by-line explanation**

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS postgis;
```

`pgcrypto` provides `gen_random_uuid()`, used as the `DEFAULT` for every UUID surrogate primary
key across the schema. `pg_trgm` is trigram indexing, used for the `GIN (... gin_trgm_ops)`
fuzzy/partial-text-search indexes (e.g. `master_data.value_name`, `state.state_name`,
`district.district_name`, `city_village.city_village_name`,
`organization.organization_name`). `btree_gin` allows GIN indexes over ordinary scalar types
(not just arrays/tsvector), enabling future composite GIN indexes that mix trigram and scalar
columns. `postgis` adds geospatial types/functions — not yet consumed by any table
(`organization.latitude`/`longitude` use plain `NUMERIC(10,7)`, not a PostGIS `geometry` column)
— installed ahead of need.

```sql
CREATE SCHEMA IF NOT EXISTS nss;
ALTER SCHEMA nss OWNER TO nss_db_owner;
ALTER DATABASE nss_erp SET search_path TO nss, public;
GRANT ALL ON SCHEMA nss TO nss_db_owner;
```

`CREATE SCHEMA IF NOT EXISTS nss;` is the single schema all application tables live in (never
`public`, which is reserved for extensions per this file's own comment). `ALTER SCHEMA nss OWNER
TO nss_db_owner;` makes `nss_db_owner` the schema owner, so it can subsequently `CREATE TABLE`
inside it without additional grants. `ALTER DATABASE nss_erp SET search_path TO nss, public;`
sets the *database-level* default `search_path`, so any new session connecting to `nss_erp`
resolves unqualified table names against `nss` first, then `public`, without each client having
to `SET search_path` explicitly. `GRANT ALL ON SCHEMA nss TO nss_db_owner;` is an explicit
schema-level privilege grant (`CREATE`/`USAGE`) reinforcing ownership from the `ALTER SCHEMA`
statement above.

---

### database/scripts/02_build.sh + database/scripts/02_build.ps1

> **v2.0 (2026-09-12):** Organization DDL/seed phases shrink from 3 files each to 1 file each
> (`organization_type_master`/`organization_status_master` retired — see the RETIRED notices
> under `database/ddl/02_organization/`), reducing the total build from 32 to 28 `psql -f`
> invocations.

**Requirement**

The single command that builds the entire currently-implemented schema (Bootstrap RBAC +
Foundation + Organization: 16 tables + seed data) in the exact phase order defined by
`database/README.md`'s "Execution Order" table. Without this pair, an operator would have to
manually run 28 individual `psql -f` commands in the correct dependency order by hand, with no
fail-fast behavior — a single missed or reordered file would either error out obscurely (FK to
a table that doesn't exist yet) or, worse, silently succeed against a half-built schema. It
explicitly does **not** run `database/ddl/03_person/` (superseded prototype) or apply the
deferred Pass 2 audit-actor FK constraints.

**Shared logic (both scripts)**

Both accept the same four optional parameters — `DB_NAME` (default `nss_erp`), `DB_USER`
(default `nss_db_owner`), `DB_HOST` (default `localhost`), `DB_PORT` (default `5432`). The
walkthrough below shows `02_build.sh`; the PowerShell version (`02_build.ps1`) is mechanically
equivalent — same files, same order, same behavior — see the platform-differences table after
the walkthrough for exactly how each mechanic is re-expressed in PowerShell syntax.

```bash
set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_db_owner}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DDL_BASE="${REPO_ROOT}/database/ddl"
SEED_BASE="${REPO_ROOT}/database/seed"

if [ -z "${PGPASSWORD:-}" ]; then
    read -rsp "Password for ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}: " PGPASSWORD
    echo ""
    export PGPASSWORD
fi

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v ON_ERROR_STOP=1"
```

`set -euo pipefail` is strict mode. The four parameters resolve from positional arguments with
bash parameter-expansion defaults. `SCRIPT_DIR`/`REPO_ROOT`/`DDL_BASE`/`SEED_BASE` resolve
absolute paths regardless of the caller's working directory. The password block prompts once for
a password if `PGPASSWORD` isn't already set in the environment, then exports it so every
subsequent `psql` invocation reuses it without re-prompting. `PSQL` bakes `-v ON_ERROR_STOP=1`
into every invocation, which makes `psql` itself halt a given file's script on the first SQL
error inside that file.

```bash
run_sql() {
    local label="$1"
    local file="$2"
    local output
    total=$((total + 1))
    if output=$(${PSQL} -f "${file}" 2>&1); then
        echo -e "  ${GREEN}[OK]${NC}   ${label}"
    else
        echo -e "  ${RED}[FAIL]${NC} ${label}"
        echo -e "  ${RED}Error:${NC}"
        echo "${output}" | sed 's/^/         /'
        failed=$((failed + 1))
        echo -e "  ${RED}Aborting — fix the above error before continuing.${NC}"
        exit 1
    fi
}
```

The `run_sql` helper (`Invoke-Sql` in PowerShell) invokes `psql ... -f <file>`, prints a colored
`[OK]`/`[FAIL]` line per file, and — critically — **aborts the entire script on the first
failure** (`exit 1` immediately, no attempt to continue past a broken statement).

```bash
FOUNDATION_DDL=(
    "master_category|02_master_category.sql"
    "system_setting|03_system_setting.sql"
    ...
    "city_village_postal_code_map|13_city_village_postal_code_map.sql"
)
for entry in "${FOUNDATION_DDL[@]}"; do
    label="${entry%%|*}"
    file="${entry##*|}"
    run_sql "${label}" "${DDL_BASE}/01_foundation/${file}"
done
```

Files execute in exactly this order, matching `database/README.md`:

- **Phase 0** — Bootstrap RBAC DDL (`01_role_master.sql`, `02_permission_master.sql`,
  `03_role_permission.sql`), then Bootstrap RBAC seed (same three files' `seed/` counterparts,
  same order).
- **Phase 1** — Foundation DDL, 12 files in dependency order (`02_master_category.sql` through
  `13_city_village_postal_code_map.sql`), driven by the label/file array shown above so the
  runner and its printed label stay in sync.
- **Phase 2** — Foundation seed, 8 files in dependency order (categories → data → sequences →
  country → state → district → settings → postal codes).
- **Phase 3** — Organization DDL, 1 file (`03_organization.sql`; the retired
  `01_organization_type_master.sql`/`02_organization_status_master.sql` type/status masters are
  no longer part of this phase — type/status now resolve through Foundation's `master_data`,
  seeded in Phase 2).
- **Phase 4** — Organization seed, 1 file, same order.

```bash
if [ "$failed" -eq 0 ]; then
    echo -e "  ${GREEN}Database build completed successfully.${NC}"
    echo ""
    echo -e "  ${YELLOW}Not executed (future phases):${NC}"
    echo "    - Person DDL (03_person/ is superseded — awaiting rewrite)"
    echo "    - Authentication, Administration, remaining modules"
    echo "    - Pass 2 audit-actor FK constraints"
    exit 0
else
    echo -e "  ${RED}Database build FAILED (${failed} errors).${NC}"
    exit 1
fi
```

Finally the script prints a summary (`total`/`failed` counts) and, on success, explicitly lists
what was **not** executed: Person DDL (superseded, awaiting rewrite), Authentication/
Administration/remaining modules, and Pass 2 audit-actor FK constraints. It exits `0` on full
success, `1` on any failure.

The scripts are **not idempotent** — re-running against an already-built database fails on the
first `CREATE TABLE` (by design; a fresh rebuild means drop-and-recreate the database first, not
re-run this script).

**Platform-mechanical differences only**

| Aspect | `02_build.sh` | `02_build.ps1` |
|---|---|---|
| Strict-mode | `set -euo pipefail` | `$ErrorActionPreference = "Stop"` |
| Password prompt | `read -rsp "..." PGPASSWORD` (hidden stdin read) | `Read-Host -AsSecureString` + `Marshal::SecureStringToBSTR`/`PtrToStringAuto` to decode to plaintext for `$env:PGPASSWORD` |
| Failure detection | `if output=$(${PSQL} -f "${file}" 2>&1); then ... else ...` (captures combined stdout/stderr, checks exit code) | `& psql ... -f $File 2>&1` then check `$LASTEXITCODE -eq 0` |
| File-list structure | Bash array of `"label|file"` strings split with `${entry%%|*}` / `${entry##*|}` | PowerShell array of two-element arrays `@("label","file")`, indexed `$entry[0]`/`$entry[1]` |
| Color output | ANSI escape codes (`\033[0;32m` etc.) via `echo -e` | `-ForegroundColor` parameter on `Write-Host` |
| Path resolution | `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` then `../..` | `Split-Path -Parent $MyInvocation.MyCommand.Path` then `Resolve-Path "...\..\.."` |

No logic differs between the two — same files, same order, same abort-on-first-failure
behavior, same "not executed" disclosure at the end.

---

### database/scripts/03_validate.sh + database/scripts/03_validate.ps1

> **v2.0 (2026-09-12):** Organization's row-count/FK checks updated for the org-to-master-data
> migration — `organization_type_master`/`organization_status_master` checks replaced by two
> FK-integrity checks against `nss.master_data`; Foundation's `master_category`/`master_data`/
> `id_sequence_master` row-count floors raised (12/74/11) to match the new `ORGANIZATION_TYPE`
> category, expanded `STATUS` category, and the two new `id_sequence_master` rows.

**Requirement**

A read-only post-build check that the schema built by `02_build.*` is structurally and
referentially correct — table existence, seeded row counts, uniqueness, and FK integrity —
without requiring a human to open `psql` and run ad hoc queries. Without this pair, a build that
silently seeded the wrong number of rows, left an orphaned FK, or introduced a duplicate
"unique" value would only surface later as an obscure application bug. It performs **no writes**
— it must be run after `02_build.*`, never instead of it.

**Shared logic (both scripts)**

Same `DB_NAME`/`DB_USER`/`DB_HOST`/`DB_PORT` parameters and password-prompt pattern as the build
scripts, but `psql` is invoked with `-t -A` (tuples-only, unaligned output) so every query result
comes back as a single bare scalar the shell can parse directly, e.g. `t`/`f` for booleans or a
bare integer for counts. The walkthrough below shows `03_validate.sh`; `03_validate.ps1` is
mechanically equivalent (see the platform-differences table below).

```bash
check_table_exists() {
    local table="$1"
    local result
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nss' AND table_name = '${table}');" 2>&1 || echo "f")
    if [ "$result" = "t" ]; then
        log_pass "${table} exists"
    else
        log_fail "${table} MISSING"
    fi
}
```

`check_table_exists(table)` queries `information_schema.tables` for `table_schema = 'nss' AND
table_name = '<table>'`; PASS/FAIL.

```bash
check_row_count() {
    local table="$1"
    local expected="$2"
    local count
    count=$(${PSQL} -c "SELECT COUNT(*) FROM nss.${table};" 2>&1 || echo "ERROR")
    if [ "$count" = "ERROR" ]; then
        log_fail "${table}: query failed"
    elif [ "$count" -ge "$expected" ] 2>/dev/null; then
        log_pass "${table}: ${count} rows (expected >= ${expected})"
    else
        log_warn "${table}: ${count} rows (expected >= ${expected})"
    fi
}
```

`check_row_count(table, expected)` runs `SELECT COUNT(*) FROM nss.<table>`; PASS if `count >=
expected`, otherwise **WARN** (not FAIL — having more rows than the frozen seed count, e.g. from
later test data, is not treated as an error).

```bash
check_no_duplicates() {
    local table="$1"
    local column="$2"
    local dups
    dups=$(${PSQL} -c "SELECT COUNT(*) FROM (SELECT ${column} FROM nss.${table} GROUP BY ${column} HAVING COUNT(*) > 1) x;" 2>&1 || echo "ERROR")
    if [ "$dups" = "0" ]; then
        log_pass "${table}: no duplicate ${column}"
    elif [ "$dups" = "ERROR" ]; then
        log_fail "${table}: duplicate check failed"
    else
        log_fail "${table}: ${dups} duplicate ${column} values"
    fi
}
```

`check_no_duplicates(table, column)` groups by `<column>` with `HAVING COUNT(*) > 1` and counts
the groups; PASS if `0`.

```bash
check_fk_integrity() {
    local label="$1"
    local query="$2"
    local orphans
    orphans=$(${PSQL} -c "${query}" 2>&1 || echo "ERROR")
    if [ "$orphans" = "0" ]; then
        log_pass "${label}: FK integrity valid"
    elif [ "$orphans" = "ERROR" ]; then
        log_fail "${label}: FK check failed"
    else
        log_fail "${label}: ${orphans} orphaned rows"
    fi
}
```

`check_fk_integrity(label, query)` runs a caller-supplied `LEFT JOIN ... WHERE <parent>.pk IS
NULL` orphan-count query; PASS if `0`.

```bash
check_column_exists() {
    local table="$1"
    local column="$2"
    local result
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = '${table}' AND column_name = '${column}');" 2>&1 || echo "f")
    if [ "$result" = "t" ]; then
        log_pass "${table}.${column} present"
    else
        log_fail "${table}.${column} MISSING"
    fi
}
```

`check_column_exists(table, column)` queries `information_schema.columns`; used only for the two
Pass-1 deferred columns on `document_master` (`person_pk`, `uploaded_by_sangha_sevi_pk`) that
exist as nullable columns but don't yet have their FK constraints attached (Pass 2, deferred
until `sangha_sevi` exists).

Checks run in three module blocks, matching `database/README.md`'s module table:

```bash
check_fk_integrity "role_permission -> role_master" \
    "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.role_master rm ON rp.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
```

1. **Bootstrap RBAC** — 3 tables exist; `role_master` has ≥ 8 rows; no duplicate `role_code`;
   `role_permission → role_master` and `role_permission → permission_master` FK integrity (the
   call above is the actual FK-integrity query used for the first of those two checks).
2. **Foundation** — 11 tables exist; row-count floors matching the frozen seed
   (`master_category` ≥ 13, `master_data` ≥ 82, `id_sequence_master` ≥ 11, `country` ≥ 5,
   `state` ≥ 112, `district` ≥ 780, `system_setting` ≥ 4, `postal_code` ≥ 17 800,
   `city_village` ≥ 673 000); no duplicate
   `category_code`/`country_code`/`sequence_code`/`postal_code`; FK integrity for `master_data →
   master_category`, `state → country`, `district → state`, `postal_code → state`,
   `city_village → postal_code`, `city_village → district`; and the two deferred-column
   existence checks on `document_master`. Under the Simplified Geography Model (2026-10-02)
   there is no `postal_code → country` check any more — `postal_code` has no `country_pk`
   column, so country integrity is covered transitively by `postal_code → state` plus `state →
   country` — and the `city_village` checks use the `WHERE fk_col IS NOT NULL AND parent.pk IS
   NULL` form, since both `district_pk` and `postal_code_pk` are nullable there.
   `master_category`'s floor rose from 11 to 13 (added `ORGANIZATION_TYPE` and `BLOOD_GROUP` categories) and
   `master_data`'s from 58 to 82 (new `ORGANIZATION_TYPE` values, expanded `STATUS`
   category replacing the smaller `MEMBERSHIP_STATUS`, plus 8 `BLOOD_GROUP` values); `id_sequence_master`'s floor rose from
   9 to 11 (`PARIBARIK_ASANA`, `PARIBARIK_SANGHA`).
3. **Organization** — 1 table exists (`organization` — type/status now live in Foundation's
   `master_data`, so their row counts are validated as part of the Foundation `master_data`
   check above, not here); row count (3 orgs); no duplicate `organization_code`; FK integrity
   for `organization → master_data` (type, i.e. `organization_type_master_data_pk`),
   `organization → master_data` (status, i.e. `status_master_data_pk`), `organization →
   country`, `organization → city_village`, `organization → postal_code` (the last two use
   `WHERE fk_col IS NOT NULL AND parent.pk IS NULL` since those FKs are nullable — an org with
   no `city_village_pk` set is not an orphan). The two `master_data` FK-integrity checks both
   join against the same `nss.master_data` table (once per FK column), rather than against two
   separate dedicated tables as before the migration.

Finally prints `Passed`/`Warnings`/`Failed` counts; exits `0` if `fail_count = 0` (even with
warnings), `1` otherwise. The file header instructs future maintainers to extend this script
whenever new modules are added to `02_build.*`.

**Platform-mechanical differences only**

| Aspect | `03_validate.sh` | `03_validate.ps1` |
|---|---|---|
| Query execution | `${PSQL} -c "<query>"` with `\|\| echo "ERROR"` fallback on command failure | `Invoke-PsqlQuery` function checking `$LASTEXITCODE -ne 0` → returns `"ERROR"` |
| Numeric comparison | `[ "$count" -ge "$expected" ] 2>/dev/null` | `[int]$count -ge $Expected` |
| Logging functions | `log_pass`/`log_fail`/`log_warn` (snake_case, increment global counters via `$((...))`) | `Log-Pass`/`Log-Fail`/`Log-Warn` (PowerShell Verb-Noun convention, increment via `$script:pass_count++`) |
| Colors | ANSI escapes | `-ForegroundColor` |

Every query string, every expected threshold, and every check's pass/fail semantics are
identical between the two — this is the same validation matrix expressed in two shells.

---

### database/scripts/04_grant_backend.sql

**Requirement**

Grants the FastAPI runtime role `nss_db_backend` the minimum privilege it needs to actually read
data — `SELECT` on the `nss` schema's tables. Run as `nss_db_owner` (or superuser), after
`02_build.*` completes. Without this file, `nss_db_backend` can authenticate (it was granted
`CONNECT` in `00_create_database.sql`) but every query the API issues fails with "permission
denied for table X", because table ownership by `nss_db_owner` does not implicitly grant any
access to other roles. Comment in the file notes Tier 0 is `SELECT`-only by design; later tiers
add `INSERT`/`UPDATE` as write endpoints are implemented. Idempotent — safe to re-run.

**Line-by-line explanation**

```sql
GRANT USAGE ON SCHEMA nss TO nss_db_backend;
```

Schema-level `USAGE` is a separate privilege from table-level grants; without it,
`nss_db_backend` cannot even resolve `nss.<table>` names to look up privileges, regardless of
what table grants exist.

```sql
GRANT SELECT ON ALL TABLES IN SCHEMA nss TO nss_db_backend;
```

Retroactively grants `SELECT` on every table that exists in `nss` *at the moment this statement
runs* — i.e. every table created by `02_build.*` up to this point.

```sql
ALTER DEFAULT PRIVILEGES IN SCHEMA nss
    GRANT SELECT ON TABLES TO nss_db_backend;
```

Forward-looking: registers a default-privilege rule so that any table `nss_db_owner` creates in
`nss` *after* this statement runs (e.g. a future Organization or Person table) is automatically
`SELECT`-granted to `nss_db_backend` without needing to re-run the previous statement.

---

### database/ddl/00_bootstrap/01_role_master.sql

**Requirement**

Defines `nss.role_master` — the catalogue of application RBAC roles (e.g.
`NSS_ERP_ADMIN`). Depth 0 (no FK dependencies) — it's the first table in the entire build
because `role_permission` (Depth 1) needs it to exist. Without this table there is no RBAC role
catalogue at all; the 10 frozen roles seeded later would have nowhere to live, and
`role_permission` couldn't be created (its FK targets this table).

**Line-by-line explanation**

```sql
CREATE TABLE nss.role_master
(
    role_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    role_code VARCHAR(50) NOT NULL,

    role_name VARCHAR(100) NOT NULL,

    role_class VARCHAR(30) NOT NULL,

    scope_level VARCHAR(30) NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns, in order:
- `role_master_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()` — surrogate key, auto-generated.
- `role_code VARCHAR(50) NOT NULL` — the business identifier, e.g. `NSS_ERP_ADMIN`. Required.
- `role_name VARCHAR(100) NOT NULL` — human-readable name, e.g. `NSS ERP Administrator`.
- `role_class VARCHAR(30) NOT NULL` — restricted by `chk_role_master_class` (see below).
- `scope_level VARCHAR(30) NULL` — optional; restricted by `chk_role_master_scope_level` when
  present.
- `description TEXT NULL` — free-text, optional.
- `display_order INTEGER NOT NULL DEFAULT 0` — UI sort order.
- Audit block: `created_at`, `created_by_sangha_sevi_pk`, `updated_at`,
  `updated_by_sangha_sevi_pk`, `deleted_at`, `deleted_by_sangha_sevi_pk`, `is_active`. The four
  `*_sangha_sevi_pk` actor columns are nullable UUIDs with **no FK constraint** — this is the
  Pass 1 half of the project's documented Two-Pass DDL Strategy; the FK to `sangha_sevi` will be
  added in Pass 2, once that table exists and has at least one row (the bootstrap admin).

```sql
    -- Unique constraints
    CONSTRAINT uq_role_master_code
        UNIQUE (role_code),

    CONSTRAINT uq_role_master_name
        UNIQUE (role_name),

    -- CHECK constraints
    CONSTRAINT chk_role_master_class
        CHECK (role_class IN ('SYSTEM', 'ORGANIZATIONAL')),

    CONSTRAINT chk_role_master_scope_level
        CHECK
        (
            scope_level IS NULL
            OR
            scope_level IN ('NSS-WIDE', 'KENDRA', 'ANCHALIKA', 'ZILLA', 'SAKHA', 'PATHA_CHAKRA')
        ),

    CONSTRAINT chk_role_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);
```

`uq_role_master_code UNIQUE (role_code)` and `uq_role_master_name UNIQUE (role_name)` mean both
the business code and the display name must be unique. `chk_role_master_class CHECK (role_class
IN ('SYSTEM', 'ORGANIZATIONAL'))` allows only two role classes. `chk_role_master_scope_level
CHECK (scope_level IS NULL OR scope_level IN ('NSS-WIDE', 'KENDRA', 'ANCHALIKA', 'ZILLA',
'SAKHA', 'PATHA_CHAKRA'))` means the value is either unset, or one of the six organizational
scope levels that mirror the Organization module's hierarchy. `chk_role_master_soft_delete`
enforces the soft-delete invariant: a row can never be inactive without a deletion timestamp,
nor active with one set.

```sql
CREATE INDEX idx_role_master_active
    ON nss.role_master (is_active);

CREATE INDEX idx_role_master_code
    ON nss.role_master (role_code);

CREATE INDEX idx_role_master_class
    ON nss.role_master (role_class);
```

These three indexes support the common lookup patterns: active-only listing, lookup by code, and
filtering by SYSTEM vs ORGANIZATIONAL.

---

### database/ddl/00_bootstrap/02_permission_master.sql

**Requirement**

Defines `nss.permission_master` — the catalogue of individual application permissions, grouped
by `module_code`. Depth 0, sibling to `role_master`. Without it, `role_permission` (which maps
roles to permissions) has no permission side to reference; the permission catalogue itself is
currently seeded empty (pending the permission-catalogue freeze — see the seed file below), but
the table must still exist so the mapping table's FK can be declared.

**Line-by-line explanation**

```sql
CREATE TABLE nss.permission_master
(
    permission_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    permission_code VARCHAR(80) NOT NULL,

    permission_name VARCHAR(150) NOT NULL,

    module_code VARCHAR(50) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `permission_master_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `permission_code VARCHAR(80) NOT NULL` — business identifier for the permission.
- `permission_name VARCHAR(150) NOT NULL` — human-readable name.
- `module_code VARCHAR(50) NOT NULL` — which application module the permission belongs to (no
  CHECK restricting the value set — module codes are open-ended, unlike `role_class`).
- `description TEXT NULL`.
- `display_order INTEGER NOT NULL DEFAULT 0`.
- Same six-column audit block as `role_master` (`created_at`, `created_by_sangha_sevi_pk`,
  `updated_at`, `updated_by_sangha_sevi_pk`, `deleted_at`, `deleted_by_sangha_sevi_pk`), plus
  `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

```sql
    -- Unique constraints
    CONSTRAINT uq_permission_master_code
        UNIQUE (permission_code),

    -- CHECK constraints
    CONSTRAINT chk_permission_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);
```

`uq_permission_master_code UNIQUE (permission_code)` — only the code is guaranteed unique
(unlike `role_master`, there is no unique constraint on `permission_name`).
`chk_permission_master_soft_delete` is the same soft-delete invariant pattern as `role_master`.

```sql
CREATE INDEX idx_permission_master_active
    ON nss.permission_master (is_active);

CREATE INDEX idx_permission_master_code
    ON nss.permission_master (permission_code);

CREATE INDEX idx_permission_master_module
    ON nss.permission_master (module_code);
```

The module index supports listing all permissions for a given module.

---

### database/ddl/00_bootstrap/03_role_permission.sql

**Requirement**

Defines `nss.role_permission` — the many-to-many join between `role_master` and
`permission_master`. Depth 1 (its FKs require both parent tables to exist first, hence it's
file `03_` after `01_`/`02_`). Without it there is no way to express "role X has permission Y" —
the entire RBAC authorization model has no join table.

**Line-by-line explanation**

```sql
CREATE TABLE nss.role_permission
(
    role_permission_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    role_master_pk UUID NOT NULL,

    permission_master_pk UUID NOT NULL,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `role_permission_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `role_master_pk UUID NOT NULL` — FK side 1.
- `permission_master_pk UUID NOT NULL` — FK side 2.
- Audit block is a **subset** of the other two Bootstrap tables: `created_at`,
  `created_by_sangha_sevi_pk`, `deleted_at`, `deleted_by_sangha_sevi_pk`, `is_active` — notably
  **no `updated_at`/`updated_by_sangha_sevi_pk`**. A role-permission mapping is either created
  or (soft-)deleted; it is not "updated" in place, so there's no update-tracking pair.

```sql
    -- Foreign keys
    CONSTRAINT fk_role_permission_role
        FOREIGN KEY (role_master_pk)
        REFERENCES nss.role_master (role_master_pk),

    CONSTRAINT fk_role_permission_permission
        FOREIGN KEY (permission_master_pk)
        REFERENCES nss.permission_master (permission_master_pk),

    -- Unique constraint: no duplicate mapping
    CONSTRAINT uq_role_permission_mapping
        UNIQUE (role_master_pk, permission_master_pk),

    -- CHECK constraints
    CONSTRAINT chk_role_permission_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);
```

`fk_role_permission_role` and `fk_role_permission_permission` are the two parent-table FKs that
make this table Depth 1. `uq_role_permission_mapping UNIQUE (role_master_pk,
permission_master_pk)` means a given role/permission pair can only be mapped once (prevents
duplicate grants). `chk_role_permission_soft_delete` is the same soft-delete invariant as the
other Bootstrap tables.

```sql
CREATE INDEX idx_role_permission_role
    ON nss.role_permission (role_master_pk);

CREATE INDEX idx_role_permission_permission
    ON nss.role_permission (permission_master_pk);

CREATE INDEX idx_role_permission_active
    ON nss.role_permission (is_active);
```

These support "all permissions for role X" and "all roles with permission Y" lookups in either
direction.

---

### database/seed/00_bootstrap/01_permission_master.sql

**Requirement**

Reserves the seed slot for `permission_master` in the build order (run by `02_build.*` between
the Bootstrap DDL phase and the `role_master` seed) so the phase numbering stays stable once the
permission catalogue is frozen. It currently inserts nothing.

**Line-by-line explanation**

```sql
-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 01_permission_master.sql (seed)
-- Seed: Permission catalogue
-- Authority: SOL-ARCH-011 §4, SOL-ADMIN-004 §9.5
--
-- STATUS: EMPTY — permission catalogue NOT YET FROZEN
--
-- This file will be populated when the permission
-- catalogue is approved. Until then, no permission
-- rows are seeded.
-- =====================================================
```

The file contains only this header comment block — no `INSERT` statement. It will be populated
once the permission catalogue is approved (SOL-ADMIN-004 §9.5). Row count: **0**.

---

### database/seed/00_bootstrap/02_role_master.sql

**Requirement**

Seeds the 8 frozen application RBAC roles into `role_master` — the concrete rows that
`NSS_ERP_ADMIN` and the other administrative identities resolve to. Without this file the
Bootstrap Verification UI's `/api/v1/bootstrap/roles` endpoint would return an empty list, and
there would be no role for the eventual first administrator account to be assigned.

**Line-by-line explanation**

```sql
INSERT INTO nss.role_master
    (role_code, role_name, role_class, scope_level, description, display_order)
VALUES
    ('NSS_ERP_ADMIN',
     'NSS ERP Administrator',
     'SYSTEM',
     'NSS-WIDE',
     'System-wide ERP administrator with all application permissions',
     1),

    ('NSS_ERP_KENDRA_ADMIN',
     'Kendra Administrator',
     'ORGANIZATIONAL',
     'KENDRA',
     'Administrative authority scoped to a specific Kendra',
     4),

    -- ...5 more rows, same shape...
```

The column list supplies all six non-audit, non-PK columns explicitly — `role_master_pk`,
`is_active`, and the audit timestamps all fall back to their `DEFAULT`s (a fresh UUID, `TRUE`,
`CURRENT_TIMESTAMP` respectively); the nullable audit-actor columns stay `NULL` since no
`sangha_sevi` exists yet to attribute the insert to.

**Row count: 8** (all 8 rows listed — this is a small, fully-enumerable seed file):

| role_code | role_name | role_class | scope_level | display_order |
|---|---|---|---|---|
| `NSS_ERP_ADMIN` | NSS ERP Administrator | SYSTEM | NSS-WIDE | 1 |
| `NSS_ERP_AUDITOR` | Auditor | SYSTEM | NSS-WIDE | 2 |
| `NSS_ERP_REPORT_VIEWER` | Report Viewer | SYSTEM | NSS-WIDE | 3 |
| `NSS_ERP_KENDRA_ADMIN` | Kendra Administrator | ORGANIZATIONAL | KENDRA | 4 |
| `NSS_ERP_ANCHALIKA_ADMIN` | Anchalika Administrator | ORGANIZATIONAL | ANCHALIKA | 5 |
| `NSS_ERP_ZILLA_ADMIN` | Zilla Administrator | ORGANIZATIONAL | ZILLA | 6 |
| `NSS_ERP_SAKHA_ADMIN` | Sakha Administrator | ORGANIZATIONAL | SAKHA | 7 |
| `NSS_ERP_PATHA_CHAKRA_ADMIN` | Patha Chakra Administrator | ORGANIZATIONAL | PATHA_CHAKRA | 8 |

Pattern: the three `SYSTEM`/`NSS-WIDE` roles (admin, auditor, report viewer) are global; the five
`ORGANIZATIONAL` roles each scope to exactly one of the five organizational levels defined by
`chk_role_master_scope_level` in the DDL. Every `scope_level` value used here is one of the six
allowed by that CHECK constraint (`PATHA_CHAKRA` is used; `SAKHA_ASANA` — a seventh
organization type seeded later in Organization — has no corresponding admin role at all,
which is a notable asymmetry worth flagging rather than an error).

---

### database/seed/00_bootstrap/03_role_permission.sql

**Requirement**

Reserves the seed slot for `role_permission` mappings, run after `role_master` is seeded.
Currently empty because it structurally depends on `permission_master` being populated first,
and that catalogue isn't frozen yet.

**Line-by-line explanation**

```sql
-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 03_role_permission.sql (seed)
-- Seed: Role-to-permission mappings
-- Authority: SOL-ARCH-011 §4, SOL-ADMIN-004 §10
--
-- STATUS: EMPTY — depends on permission catalogue
--
-- This file will be populated after 01_permission_master
-- seed is frozen. Role-permission mappings cannot exist
-- without permissions.
-- =====================================================
```

Header-comment-only file, no `INSERT`. Role-permission mappings cannot exist without
permissions. Row count: **0**.

---

### database/ddl/01_foundation/02_master_category.sql

**Requirement**

Defines `nss.master_category` — the top level of the generic two-table
lookup-value pattern (`master_category` + `master_data`) used throughout the schema for
enumerated reference data (gender, marital status, document type, etc.) instead of one
hand-rolled lookup table per concept. Depth 0, first Foundation table. Without it, `master_data`
(Depth 1) has nothing to categorize its values under, and none of the generic
category/value-driven master data used by Person, Membership, etc. designs would have a home.

**Line-by-line explanation**

```sql
CREATE TABLE nss.master_category
(
    master_category_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    category_code VARCHAR(50) NOT NULL,

    category_name VARCHAR(100) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `master_category_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `category_code VARCHAR(50) NOT NULL` — e.g. `GENDER`.
- `category_name VARCHAR(100) NOT NULL` — e.g. `Gender`.
- `description TEXT NULL`.
- `display_order INTEGER NOT NULL DEFAULT 0`.
- `created_at`, `updated_at`, `deleted_at`, `is_active` — note this is a **shorter** audit block
  than the Bootstrap tables: no `created_by_sangha_sevi_pk` / `updated_by_sangha_sevi_pk` /
  `deleted_by_sangha_sevi_pk` actor columns at all. Foundation's reference-data tables generally
  omit actor tracking (see also `system_setting`, `id_sequence_master`, `country`,
  `master_data`, `state`, `district`, `city_village`, `postal_code`) — only `document_master`
  (`uploaded_by_sangha_sevi_pk`) and `field_change_log` (`changed_by_sangha_sevi_pk`) carry actor
  references in this module.

```sql
    CONSTRAINT uq_master_category_code
        UNIQUE (category_code),

    CONSTRAINT uq_master_category_name
        UNIQUE (category_name),

    CONSTRAINT chk_master_category_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_master_category_active
    ON nss.master_category (is_active);

CREATE INDEX idx_master_category_code
    ON nss.master_category (category_code);
```

`uq_master_category_code` and `uq_master_category_name` are both unique. `chk_master_category_
soft_delete` is the standard soft-delete invariant. The two indexes are on `is_active` and
`category_code`.

---

### database/ddl/01_foundation/03_system_setting.sql

**Requirement**

Defines `nss.system_setting` — a generic key/value configuration store (e.g. current membership
year, password policy). Depth 0. Without it there is no database-backed place for
application-wide configuration that needs to be readable/editable without a code deploy;
everything would have to be a hardcoded constant, which conflicts with the project's
"Configuration Over Hardcoding" frozen principle.

**Line-by-line explanation**

```sql
CREATE TABLE nss.system_setting
(
    system_setting_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    setting_key VARCHAR(100) NOT NULL,

    setting_value TEXT NOT NULL,

    description TEXT NULL,

    data_type VARCHAR(20) NOT NULL
        DEFAULT 'STRING',

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `system_setting_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `setting_key VARCHAR(100) NOT NULL` — e.g. `CURRENT_MEMBERSHIP_YEAR`.
- `setting_value TEXT NOT NULL` — stored as text regardless of logical type; `data_type` (below)
  tells consumers how to interpret it.
- `description TEXT NULL`.
- `data_type VARCHAR(20) NOT NULL DEFAULT 'STRING'` — restricted by CHECK below.
- `created_at`, `updated_at`, `deleted_at`, `is_active` — standard four-column audit block.

```sql
    CONSTRAINT uq_system_setting_key
        UNIQUE (setting_key),

    CONSTRAINT chk_system_setting_data_type
        CHECK
        (
            data_type IN
            (
                'STRING',
                'INTEGER',
                'BOOLEAN',
                'DATE',
                'JSON'
            )
        ),

    CONSTRAINT chk_system_setting_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_system_setting_active
    ON nss.system_setting (is_active);

CREATE INDEX idx_system_setting_key
    ON nss.system_setting (setting_key);
```

`uq_system_setting_key UNIQUE (setting_key)`. `chk_system_setting_data_type CHECK (data_type IN
('STRING', 'INTEGER', 'BOOLEAN', 'DATE', 'JSON'))` is the five type-tag values a consumer can
expect. `chk_system_setting_soft_delete` is the standard invariant. Indexes cover `is_active` and
`setting_key`.

---

### database/ddl/01_foundation/04_id_sequence_master.sql

> **v2.0 (2026-09-12):** `chk_id_sequence_padding` loosened from `BETWEEN 4 AND 12` to
> `BETWEEN 2 AND 12` to allow the new `PARIBARIK_SANGHA` sequence's 3-digit padding (and
> `PARIBARIK_ASANA`'s 5-digit padding, which already fit the old range).

**Requirement**

Defines `nss.id_sequence_master` — a table-driven business-ID generator, one row per business
entity that needs a permanent, human-readable, sequential identifier (e.g. Sangha Sevi IDs,
Anchalika codes). This directly implements the project's frozen "Permanent Business Identifiers"
principle without hardcoding a PostgreSQL `SEQUENCE` per entity type — every sequence's prefix,
current counter, and zero-padding width are configurable data, not schema.

**Line-by-line explanation**

```sql
CREATE TABLE nss.id_sequence_master
(
    id_sequence_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sequence_code VARCHAR(50) NOT NULL,

    sequence_name VARCHAR(100) NOT NULL,

    prefix VARCHAR(20) NOT NULL,

    current_value BIGINT NOT NULL
        DEFAULT 0,

    padding_length INTEGER NOT NULL
        DEFAULT 8,

    description TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `id_sequence_master_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `sequence_code VARCHAR(50) NOT NULL` — e.g. `SANGHA_SEVI`.
- `sequence_name VARCHAR(100) NOT NULL` — e.g. `Sangha Sevi Code`.
- `prefix VARCHAR(20) NOT NULL` — e.g. `SS`, prepended to the generated number.
- `current_value BIGINT NOT NULL DEFAULT 0` — the last-issued counter value; the application
  layer increments this atomically when issuing a new ID.
- `padding_length INTEGER NOT NULL DEFAULT 8` — how many digits the numeric part is zero-padded
  to.
- `description TEXT NULL`.
- `created_at`, `updated_at`, `deleted_at`, `is_active` — standard four-column audit block.

```sql
    CONSTRAINT uq_id_sequence_code
        UNIQUE (sequence_code),

    CONSTRAINT uq_id_sequence_name
        UNIQUE (sequence_name),

    CONSTRAINT chk_id_sequence_padding
        CHECK (padding_length BETWEEN 2 AND 12),

    CONSTRAINT chk_id_sequence_current_value
        CHECK (current_value >= 0),

    CONSTRAINT chk_id_sequence_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_id_sequence_active
    ON nss.id_sequence_master (is_active);

CREATE INDEX idx_id_sequence_code
    ON nss.id_sequence_master (sequence_code);
```

`uq_id_sequence_code` and `uq_id_sequence_name` are both unique. `chk_id_sequence_padding CHECK
(padding_length BETWEEN 2 AND 12)` bounds how wide a generated ID's numeric portion can be — the
lower bound was loosened from 4 to 2 in v2.0 to accommodate `PARIBARIK_SANGHA`'s 3-digit
padding. `chk_id_sequence_current_value CHECK (current_value >= 0)` means the counter can never
go negative. `chk_id_sequence_soft_delete` is the standard invariant. Indexes cover `is_active`
and `sequence_code`.

---

### database/ddl/01_foundation/05_country.sql

**Requirement**

Defines `nss.country` — the root of the location hierarchy (`country` → `state` → `district` →
`city_village` → `postal_code`). Depth 0. Without it, `state` (which FKs to it) cannot
exist, and the entire address/location model for Person, Organization, etc. has no anchor.
Note that `postal_code` does **not** FK to `country` directly — since the Simplified Geography
Model (2026-10-02) a PIN's country is reached via `postal_code.state_pk → state.country_pk`.

**Line-by-line explanation**

```sql
CREATE TABLE nss.country
(
    country_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_code CHAR(2) NOT NULL,

    country_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `country_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `country_code CHAR(2) NOT NULL` — fixed 2-character code, e.g. `IN`, `US` (ISO 3166-1
  alpha-2 style, though not formally constrained to the ISO list by a CHECK).
- `country_name VARCHAR(100) NOT NULL` — e.g. `India`.
- `display_order INTEGER NOT NULL DEFAULT 0`.
- `created_at`, `updated_at`, `deleted_at`, `is_active` — standard four-column audit block.

```sql
    CONSTRAINT uq_country_code
        UNIQUE (country_code),

    CONSTRAINT uq_country_name
        UNIQUE (country_name),

    CONSTRAINT chk_country_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_country_active
    ON nss.country (is_active);

CREATE INDEX idx_country_code
    ON nss.country (country_code);
```

`uq_country_code` and `uq_country_name` are both unique. `chk_country_soft_delete` is the
standard invariant. Indexes cover `is_active` and `country_code`.

---

### database/ddl/01_foundation/06_document_master.sql

**Requirement**

Defines `nss.document_master` — metadata for every uploaded/stored file in the system (photos,
ID proofs, certificates, correspondence, etc.), independent of which module owns the document.
Depth 0 by DDL classification, but logically it's a Person-module concept whose physical table
is owned by Foundation (per the file's own header note) — a deliberate split between logical
design ownership and physical DDL placement. Without it there would be no single place to
record where an uploaded file lives, what type it is, and (once Pass 2 lands) who uploaded it
and for which person.

**Line-by-line explanation**

```sql
CREATE TABLE nss.document_master
(
    document_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    document_type_code VARCHAR(50) NOT NULL,

    document_number VARCHAR(100) NULL,

    document_name VARCHAR(255) NOT NULL,

    storage_path TEXT NOT NULL,

    file_size_bytes BIGINT NULL,

    mime_type VARCHAR(100) NULL,

    version INTEGER NOT NULL
        DEFAULT 1,

    checksum VARCHAR(128) NULL,

    description TEXT NULL,

    person_pk UUID NULL,

    uploaded_by_sangha_sevi_pk UUID NULL,

    uploaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `document_master_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `document_type_code VARCHAR(50) NOT NULL` — links conceptually (not via FK) to the
  `DOCUMENT_TYPE` category in `master_data` (e.g. `PHOTO`, `ID_PROOF`).
- `document_number VARCHAR(100) NULL` — e.g. an ID-proof document's printed number; optional.
- `document_name VARCHAR(255) NOT NULL` — display name of the file.
- `storage_path TEXT NOT NULL` — where the file physically/logically lives (filesystem path,
  object-store key, etc.).
- `file_size_bytes BIGINT NULL`.
- `mime_type VARCHAR(100) NULL`.
- `version INTEGER NOT NULL DEFAULT 1` — supports re-uploaded/superseding versions of the same
  logical document; constrained by CHECK below.
- `checksum VARCHAR(128) NULL` — integrity hash of the stored file.
- `description TEXT NULL`.
- `person_pk UUID NULL` — **deferred FK** (Pass 1 nullable column, Pass 2 will attach `FOREIGN
  KEY REFERENCES person`, once the real `person` table exists — not the superseded prototype).
- `uploaded_by_sangha_sevi_pk UUID NULL` — **deferred FK**, same Pass 2 treatment, referencing
  the eventual `sangha_sevi` table.
- `uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP` — separate from `created_at`;
  this records when the *file* was uploaded, which may conceptually differ from row-creation
  time in some future workflow even though today they'd be set at the same moment.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`, `updated_at TIMESTAMPTZ NULL`,
  `deleted_at TIMESTAMPTZ NULL`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

```sql
    CONSTRAINT chk_document_version_positive
        CHECK (version >= 1),

    CONSTRAINT chk_document_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_document_master_type_code
    ON nss.document_master (document_type_code);

CREATE INDEX idx_document_master_active
    ON nss.document_master (is_active);

CREATE INDEX idx_document_master_number
    ON nss.document_master (document_number)
    WHERE document_number IS NOT NULL;
```

- `chk_document_version_positive CHECK (version >= 1)`.
- `chk_document_master_soft_delete` — standard invariant.
- No FK constraints exist yet at all in this file (the two candidate FK columns are Pass-1
  nullable placeholders only).

Indexes: `idx_document_master_type_code (document_type_code)`, `idx_document_master_active
(is_active)`, and a **partial** index `idx_document_master_number (document_number) WHERE
document_number IS NOT NULL` — avoids indexing the (likely common) `NULL` case.

Note: the file's own header comment contains a minor internal inconsistency —
it states both `Sequence: #5 of 86` and `Sequence: #5 of 87` on consecutive lines (a leftover
from a prior renumbering that wasn't fully cleaned up); it does not affect the executed DDL.

---

### database/ddl/01_foundation/07_field_change_log.sql

**Requirement**

Defines `nss.field_change_log` — a generic, cross-table field-level audit trail (which record,
which field, old value, new value, who, when, why). Depth 0 by design choice, not by accident:
the file's own header explains it deliberately carries **no FK constraints** so that any table
in the schema can be logged against without creating circular or premature dependencies. Without
it, there would be no uniform way to answer "what did this field used to be, and who changed
it" for arbitrary tables — each module would need its own bespoke history table.

**Line-by-line explanation**

```sql
CREATE TABLE nss.field_change_log
(
    field_change_log_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    table_name VARCHAR(100) NOT NULL,

    record_pk UUID NOT NULL,

    field_name VARCHAR(100) NOT NULL,

    old_value TEXT NULL,

    new_value TEXT NULL,

    change_reason TEXT NULL,

    changed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    changed_by_sangha_sevi_pk UUID NULL
);
```

- `field_change_log_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `table_name VARCHAR(100) NOT NULL` — which table the changed row belongs to, stored as plain
  text (not an FK to `information_schema`, obviously — it's metadata about metadata).
- `record_pk UUID NOT NULL` — the PK value of the changed row in that table.
- `field_name VARCHAR(100) NOT NULL` — which column changed.
- `old_value TEXT NULL` / `new_value TEXT NULL` — both stored as text regardless of the
  original column's type, so this table can log changes to any column of any type uniformly.
- `change_reason TEXT NULL` — optional free-text justification.
- `changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.
- `changed_by_sangha_sevi_pk UUID NULL` — the actor, again with **no FK constraint** (by
  explicit design here, unlike the Bootstrap tables' Pass-1/Pass-2 deferral — this table's
  header states references are intentionally left as unconstrained UUIDs to avoid circular
  dependencies, and the application layer is responsible for referential integrity).

No constraints beyond the column `NOT NULL`s — no unique constraints, no CHECK constraints, and
notably **no `is_active`/`deleted_at`/soft-delete pattern at all**: this table is an append-only
log, not a soft-deletable entity, consistent with the project's "History Never Deleted"
principle (there is nothing to soft-delete — log rows are permanent by construction).

```sql
CREATE INDEX idx_field_change_log_table_record
    ON nss.field_change_log (table_name, record_pk);

CREATE INDEX idx_field_change_log_changed_at
    ON nss.field_change_log (changed_at);

CREATE INDEX idx_field_change_log_field
    ON nss.field_change_log (table_name, field_name);
```

Indexes: `idx_field_change_log_table_record (table_name, record_pk)` — the primary lookup
pattern ("show me the history of this specific row"); `idx_field_change_log_changed_at
(changed_at)` — time-ordered queries; `idx_field_change_log_field (table_name, field_name)` —
"show me every change to this column across all rows of this table."

---

### database/ddl/01_foundation/08_master_data.sql

**Requirement**

Defines `nss.master_data` — the value side of the `master_category`/`master_data` generic
lookup pattern; every row is one enumerated value under one category (e.g. category `GENDER` →
values `MALE`/`FEMALE`/`OTHER`). Depth 1 (depends on `master_category`). Without it, the
category table has nothing under it, and none of the enumerated reference values consumed by
Person/Membership/Family modules (gender, marital status, membership type/status, relationship
type, document type, address type) have anywhere to live.

**Line-by-line explanation**

```sql
CREATE TABLE nss.master_data
(
    master_data_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    master_category_pk UUID NOT NULL,

    value_code VARCHAR(50) NOT NULL,

    value_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `master_data_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `master_category_pk UUID NOT NULL` — FK to the owning category.
- `value_code VARCHAR(50) NOT NULL` — e.g. `MALE`.
- `value_name VARCHAR(150) NOT NULL` — e.g. `Male`.
- `description TEXT NULL`.
- `display_order INTEGER NOT NULL DEFAULT 0`.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`, `updated_at TIMESTAMPTZ NULL`,
  `deleted_at TIMESTAMPTZ NULL`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

```sql
    CONSTRAINT fk_master_data_category
        FOREIGN KEY (master_category_pk)
        REFERENCES nss.master_category (master_category_pk),

    CONSTRAINT uq_master_data_category_code
        UNIQUE (master_category_pk, value_code),

    CONSTRAINT chk_master_data_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_master_data_category
    ON nss.master_data (master_category_pk);

CREATE INDEX idx_master_data_active
    ON nss.master_data (is_active);

CREATE INDEX idx_master_data_value_code
    ON nss.master_data (value_code);

CREATE INDEX idx_master_data_value_name
    ON nss.master_data USING gin (value_name gin_trgm_ops);
```

- `fk_master_data_category FOREIGN KEY (master_category_pk) REFERENCES nss.master_category
  (master_category_pk)`.
- `uq_master_data_category_code UNIQUE (master_category_pk, value_code)` — the uniqueness scope
  is **per category**, not global: `value_code = 'ACTIVE'` can validly exist under both
  `STATUS` and (hypothetically) another category without conflict, because the
  unique constraint is composite.
- `chk_master_data_soft_delete` — standard invariant.

Indexes: `idx_master_data_category (master_category_pk)`, `idx_master_data_active (is_active)`,
`idx_master_data_value_code (value_code)`, and `idx_master_data_value_name USING gin (value_name
gin_trgm_ops)` — a trigram GIN index enabling fuzzy/partial-text search over value names (this
is the first table in the build to actually use the `pg_trgm` extension installed in
`01_extensions.sql`).

---

### database/ddl/01_foundation/09_state.sql

**Requirement**

Defines `nss.state` — states/provinces/territories under a country. Depth 1 (depends on
`country`). Without it, `district` (Depth 2, FKs to `state`) has no parent to attach to, and
the address hierarchy stops at the country level.

**Line-by-line explanation**

```sql
CREATE TABLE nss.state
(
    state_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_pk UUID NOT NULL,

    state_code VARCHAR(20) NOT NULL,

    state_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

- `state_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `country_pk UUID NOT NULL` — FK to owning country.
- `state_code VARCHAR(20) NOT NULL` — e.g. `OD` for Odisha.
- `state_name VARCHAR(100) NOT NULL` — e.g. `Odisha`.
- `display_order INTEGER NOT NULL DEFAULT 0`.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`, `updated_at TIMESTAMPTZ NULL`,
  `deleted_at TIMESTAMPTZ NULL`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

```sql
    CONSTRAINT fk_state_country
        FOREIGN KEY (country_pk)
        REFERENCES nss.country (country_pk),

    CONSTRAINT uq_state_country_code
        UNIQUE (country_pk, state_code),

    CONSTRAINT uq_state_country_name
        UNIQUE (country_pk, state_name),

    CONSTRAINT chk_state_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_state_country
    ON nss.state (country_pk);

CREATE INDEX idx_state_active
    ON nss.state (is_active);

CREATE INDEX idx_state_name
    ON nss.state USING gin (state_name gin_trgm_ops);
```

- `fk_state_country FOREIGN KEY (country_pk) REFERENCES nss.country (country_pk)`.
- `uq_state_country_code UNIQUE (country_pk, state_code)` and `uq_state_country_name UNIQUE
  (country_pk, state_name)` — both uniqueness rules are scoped **per country**, so the same
  `state_code` (e.g. `AR` is used for both India's Arkansas-equivalent Arunachal Pradesh and,
  separately, US Arkansas — see the seed data below) can coexist under different countries
  without collision.
- `chk_state_soft_delete` — standard invariant.

Indexes: `idx_state_country (country_pk)`, `idx_state_active (is_active)`, `idx_state_name USING
gin (state_name gin_trgm_ops)` (fuzzy search).

---

### database/ddl/01_foundation/10_district.sql

**Requirement**

Defines `nss.district` — districts under a state. Depth 2 (depends on `state`). Without it,
`city_village` (Depth 3) has no parent, and no Indian district-level administrative geography
exists for organization/address records to reference.

**Line-by-line explanation**

```sql
CREATE TABLE nss.district
(
    district_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    state_pk UUID NOT NULL,

    district_code VARCHAR(20) NOT NULL,

    district_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `district_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `state_pk UUID NOT NULL` (FK
to owning state); `district_code VARCHAR(20) NOT NULL`; `district_name VARCHAR(100) NOT NULL`;
`display_order INTEGER NOT NULL DEFAULT 0`; the standard four-column audit block
(`created_at`/`updated_at`/`deleted_at`/`is_active`).

```sql
    CONSTRAINT fk_district_state
        FOREIGN KEY (state_pk)
        REFERENCES nss.state (state_pk),

    CONSTRAINT uq_district_state_code
        UNIQUE (state_pk, district_code),

    CONSTRAINT uq_district_state_name
        UNIQUE (state_pk, district_name),

    CONSTRAINT chk_district_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_district_state
    ON nss.district (state_pk);

CREATE INDEX idx_district_active
    ON nss.district (is_active);

CREATE INDEX idx_district_name
    ON nss.district USING gin (district_name gin_trgm_ops);
```

Constraints: `fk_district_state FOREIGN KEY (state_pk) REFERENCES nss.state (state_pk)`;
`uq_district_state_code UNIQUE (state_pk, district_code)` and `uq_district_state_name UNIQUE
(state_pk, district_name)` — again scoped per-parent (per state), not global;
`chk_district_soft_delete` standard invariant.

Indexes: `idx_district_state (state_pk)`, `idx_district_active (is_active)`,
`idx_district_name USING gin (district_name gin_trgm_ops)`.

---

### database/ddl/01_foundation/11_city_village.sql

**Requirement**

Defines `nss.city_village` — the finest-grained named locality (city, town, or village) under a
district. Depth 3 (depends on `district`). Without it, there is no leaf-level locality node for
addresses to attach to, and `city_village_postal_code_map` (Depth 4, FKs to this table) cannot
exist.

**Line-by-line explanation**

```sql
CREATE TABLE nss.city_village
(
    city_village_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    district_pk UUID NOT NULL,

    city_village_code VARCHAR(20) NOT NULL,

    city_village_name VARCHAR(150) NOT NULL,

    city_village_type VARCHAR(20) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `city_village_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `district_pk UUID NOT
NULL` (FK to owning district); `city_village_code VARCHAR(20) NOT NULL`; `city_village_name
VARCHAR(150) NOT NULL`; `city_village_type VARCHAR(20) NOT NULL` — restricted by CHECK below;
`display_order INTEGER NOT NULL DEFAULT 0`; standard four-column audit block.

```sql
    CONSTRAINT fk_city_village_district
        FOREIGN KEY (district_pk)
        REFERENCES nss.district (district_pk),

    CONSTRAINT uq_city_village_district_code
        UNIQUE (district_pk, city_village_code),

    CONSTRAINT uq_city_village_district_name
        UNIQUE (district_pk, city_village_name),

    CONSTRAINT chk_city_village_type
        CHECK
        (
            city_village_type IN
            (
                'CITY',
                'TOWN',
                'VILLAGE'
            )
        ),

    CONSTRAINT chk_city_village_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_city_village_district
    ON nss.city_village (district_pk);

CREATE INDEX idx_city_village_active
    ON nss.city_village (is_active);

CREATE INDEX idx_city_village_name
    ON nss.city_village USING gin (city_village_name gin_trgm_ops);
```

Constraints: `fk_city_village_district FOREIGN KEY (district_pk) REFERENCES nss.district
(district_pk)`; `uq_city_village_district_code UNIQUE (district_pk, city_village_code)` and
`uq_city_village_district_name UNIQUE (district_pk, city_village_name)` — per-district scoped
uniqueness; `chk_city_village_type CHECK (city_village_type IN ('CITY', 'TOWN', 'VILLAGE'))` —
exactly three allowed locality classifications; `chk_city_village_soft_delete` standard
invariant.

Indexes: `idx_city_village_district (district_pk)`, `idx_city_village_active (is_active)`,
`idx_city_village_name USING gin (city_village_name gin_trgm_ops)`.

---

### database/ddl/01_foundation/12_postal_code.sql

**Requirement**

Defines `nss.postal_code` — PIN/postal codes, scoped to a single state. Depth 1 (depends on
`state` only). Implements the "PIN Code Geographic Model" amendment as revised by the
**Simplified Geography Model (2026-10-02)**: a PIN is one globally-unique row carrying a
pre-resolved *dominant* state (the state holding the most locality rows for that PIN, which
settles the ~29 PINs that straddle state lines). A postal code is still not tied 1:1 to a
single locality, but that relationship is now expressed by the nullable
`city_village.postal_code_pk` FK on the anchor table rather than by an M:N junction. Country is
no longer stored here — it is reached via `state_pk -> state.country_pk`. District is
deliberately **not** a column either, because PIN → District is not 1:1 (2,269 PINs legitimately
span two or more districts); district is reached through `city_village.district_pk`. Without
this table, `organization` and (in the superseded Person prototype) `person_address` have no
postal-code entity to reference.

**Line-by-line explanation**

```sql
CREATE TABLE nss.postal_code
(
    postal_code_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    state_pk UUID NOT NULL,

    postal_code VARCHAR(20) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `postal_code_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `state_pk UUID NOT NULL`
(FK) — the dominant state for this PIN, and the sole administrative parent, which is also how
country is re-derived; `postal_code VARCHAR(20) NOT NULL` — the PIN value itself, stored as text
(not numeric) since some countries' postal codes contain letters and leading zeros must be
preserved; standard four-column audit block.

```sql
    CONSTRAINT fk_postal_code_state
        FOREIGN KEY (state_pk)
        REFERENCES nss.state (state_pk),

    CONSTRAINT uq_postal_code_code
        UNIQUE (postal_code),

    CONSTRAINT chk_postal_code_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_postal_code_state
    ON nss.postal_code (state_pk);

CREATE INDEX idx_postal_code_code
    ON nss.postal_code (postal_code);

CREATE INDEX idx_postal_code_active
    ON nss.postal_code (is_active);
```

Constraints: `fk_postal_code_state FOREIGN KEY (state_pk) REFERENCES nss.state (state_pk)`;
`uq_postal_code_code UNIQUE (postal_code)` — a PIN is unique **globally**, exactly one row per
PIN, which is what makes the pre-resolved dominant state unambiguous and lets callers look a
PIN up without first knowing its country or state; `chk_postal_code_soft_delete` standard
invariant.

Indexes: `idx_postal_code_state (state_pk)`, `idx_postal_code_code (postal_code)`, and
`idx_postal_code_active (is_active)`.

---

### database/ddl/01_foundation/13_city_village_postal_code_map.sql

**Requirement**

Defines `nss.city_village_postal_code_map` — the explicit M:N join between `city_village` and
`postal_code`, implementing the PIN Code Geographic Model amendment described in
`12_postal_code.sql`'s header. Depth 4 (the deepest Foundation table — depends on both
`city_village` at Depth 3 and `postal_code` at Depth 2). Without it, there is no way to express
"this village is served by these PIN codes" (or the reverse) as a proper relation; addresses
would have to force a single PIN per locality, which the amendment explicitly rejected.

**Line-by-line explanation**

```sql
CREATE TABLE nss.city_village_postal_code_map
(
    city_village_postal_code_map_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    city_village_pk UUID NOT NULL,

    postal_code_pk UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
```

Columns: `city_village_postal_code_map_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`;
`city_village_pk UUID NOT NULL` (FK); `postal_code_pk UUID NOT NULL` (FK); `created_at
TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP` — and that's the **entire** column list; there
is no `updated_at`, `deleted_at`, or `is_active` at all. A pure join-table row is either present
or absent — there's nothing to "update" about a mapping, and removing a mapping is a hard delete
of the join row (the underlying `city_village`/`postal_code` history is preserved elsewhere via
their own soft-delete columns).

```sql
    CONSTRAINT fk_cv_pc_map_city_village
        FOREIGN KEY (city_village_pk)
        REFERENCES nss.city_village (city_village_pk),

    CONSTRAINT fk_cv_pc_map_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    CONSTRAINT uq_cv_pc_map
        UNIQUE (city_village_pk, postal_code_pk)
);

CREATE INDEX idx_cv_pc_map_city_village
    ON nss.city_village_postal_code_map (city_village_pk);

CREATE INDEX idx_cv_pc_map_postal_code
    ON nss.city_village_postal_code_map (postal_code_pk);
```

Constraints: `fk_cv_pc_map_city_village FOREIGN KEY (city_village_pk) REFERENCES
nss.city_village (city_village_pk)`; `fk_cv_pc_map_postal_code FOREIGN KEY (postal_code_pk)
REFERENCES nss.postal_code (postal_code_pk)`; `uq_cv_pc_map UNIQUE (city_village_pk,
postal_code_pk)` — prevents the same locality/PIN pair being mapped twice.

Indexes: `idx_cv_pc_map_city_village (city_village_pk)`, `idx_cv_pc_map_postal_code
(postal_code_pk)` — one index per FK direction, supporting lookups from either side of the M:N
relationship.

---

### database/seed/01_foundation/01_master_category.sql

> **v2.0 (2026-09-12):** `MEMBERSHIP_STATUS` renamed to `STATUS` and repurposed as a single
> unified ERP-wide lifecycle-status category (shared by Organization, Membership, Governance,
> etc., replacing what would otherwise have been a per-module `ORGANIZATION_STATUS` category).
> `ORGANIZATION_TYPE` added as a new category (12th), seeded for the Organization module's
> `types` endpoint, replacing the retired dedicated `organization_type_master` table.

**Requirement**

Seeds the 12 top-level lookup categories that every subsequent `master_data` value row attaches
to. Must run before `02_master_data.sql`, which resolves each value's `master_category_pk` via a
subquery on `category_code`.

**Line-by-line explanation**

```sql
INSERT INTO nss.master_category
    (category_code, category_name, description, display_order)
VALUES (...)
```

Four explicit columns per row; `master_category_pk`, `is_active`, `created_at` all default.

**Row count: 12** (all rows listed — small, fully-enumerable):

| category_code | category_name | display_order |
|---|---|---|
| `GENDER` | Gender | 1 |
| `RELATIONSHIP_TYPE` | Relationship Type | 2 |
| `MEMBERSHIP_TYPE` | Membership Type | 3 |
| `STATUS` | Status | 4 |
| `LOGIN_ROLE` | Login Role | 5 |
| `STATUS_REASON` | Status Reason | 6 |
| `WORKFLOW_STATUS` | Workflow Status | 7 |
| `DOCUMENT_TYPE` | Document Type | 8 |
| `APPLICATION_TYPE` | Application Type | 9 |
| `MARITAL_STATUS` | Marital Status | 10 |
| `ADDRESS_TYPE` | Address Type | 11 |
| `ORGANIZATION_TYPE` | Organization Type | 12 |

Notable: `STATUS` (row 4) is a **unified, ERP-wide** category — its description explicitly
reads "Unified lifecycle status for all ERP entities (organizations, memberships, governance,
etc.)" — a deliberate departure from the per-module `MEMBERSHIP_STATUS` category it replaces;
each module picks its applicable subset of `STATUS` values at the application layer rather than
owning a dedicated status category/table. Four of these categories (`LOGIN_ROLE`,
`STATUS_REASON`, `WORKFLOW_STATUS`, `APPLICATION_TYPE`) have **no corresponding rows in
`02_master_data.sql`** — they are categories reserved for future modules (Authentication,
Membership workflow) that haven't seeded values yet; 9 of the 13 categories actually have
`master_data` children today (`GENDER`, `RELATIONSHIP_TYPE`, `MEMBERSHIP_TYPE`, `STATUS`,
`DOCUMENT_TYPE`, `MARITAL_STATUS`, `ADDRESS_TYPE`, `ORGANIZATION_TYPE`, `BLOOD_GROUP`).

---

### database/seed/01_foundation/02_master_data.sql

> **v2.0 (2026-09-12):** The `MEMBERSHIP_STATUS` block (7 rows) is replaced by a `STATUS` block
> (13 rows) — the unified ERP-wide lifecycle status set, with `LAPSED`, `TRANSFERRED`,
> `RESIGNED`, `EXPELLED`, `DECEASED`, `DISSOLVED`, `EXPIRED` covering both former membership and
> organization lifecycle vocabularies (each row carries a `description` citing its NSS Bye-Law
> authority). A new `ORGANIZATION_TYPE` block (10 rows) is added, replacing the retired
> `organization_type_master` seed and adding two new types (`PARIBARIK_ASANA`,
> `PARIBARIK_SANGHA`) beyond the original 8.

**Requirement**

Seeds the 74 concrete enumerated values consumed by Person/Membership/Family/Organization
module designs (gender, marital status, address type, document type, membership type, unified
status, relationship type, organization type). Must run after `01_master_category.sql`, since
every `INSERT` resolves its `master_category_pk` via `SELECT ... FROM nss.master_category mc
... WHERE mc.category_code = '<CODE>'` joined against a `VALUES` literal — a subquery-driven
pattern rather than hardcoded UUIDs, since the category PKs are generated at category-insert
time and aren't known in advance.

**Line-by-line explanation**

Each of the eight blocks follows the identical shape:
```sql
INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES (...), (...)) AS v(value_code, value_name, display_order)
WHERE mc.category_code = '<CATEGORY>';
```
The `STATUS` and `ORGANIZATION_TYPE` blocks additionally carry a `description` column (`SELECT
mc.master_category_pk, v.value_code, v.value_name, v.description, v.display_order`) since both
sets of values benefit from a documented rationale (Bye-Law citations for `STATUS`, hierarchy
role for `ORGANIZATION_TYPE`) that the other, simpler blocks don't need.

The `CROSS JOIN` against a single-row-matching `master_category` (filtered by the `WHERE`) is
just a way to pair every literal `VALUES` row with that one category's PK without repeating the
UUID by hand.

**Row count: 74 total**, across 8 categories:

- **GENDER (3 rows):** `MALE`/Male/1, `FEMALE`/Female/2, `OTHER`/Other/3.
- **MARITAL_STATUS (5 rows):** `UNMARRIED`, `MARRIED`, `WIDOWED`, `DIVORCED`, `SEPARATED`
  (display_order 1–5, same order).
- **ADDRESS_TYPE (3 rows):** `PERMANENT`/Permanent Address/1, `CURRENT`/Current Address/2,
  `OFFICIAL`/Official Address/3.
- **DOCUMENT_TYPE (7 rows):** `PHOTO`, `ID_PROOF`, `ADDRESS_PROOF`, `CERTIFICATE`,
  `CORRESPONDENCE`, `PROPERTY_DOCUMENT`, `MEETING_MINUTES`.
- **MEMBERSHIP_TYPE (4 rows):** `PROBATIONARY`, `REGULAR`, `ASSOCIATE`, `HONORARY`.
- **STATUS (13 rows)** — the unified ERP-wide lifecycle status set, replacing the former
  per-module `MEMBERSHIP_STATUS` (7 rows): `PROPOSED`/Proposed/1, `APPROVED`/Approved/2,
  `ACTIVE`/Active/3, `INACTIVE`/Inactive/4, `SUSPENDED`/Suspended/5, `LAPSED`/Lapsed/6 (Bye-Law
  SS D(d)), `TRANSFERRED`/Transferred/7, `RESIGNED`/Resigned/8, `EXPELLED`/Expelled/9 (Bye-Law
  SS D(d)(iii)), `DECEASED`/Deceased/10 (Bye-Law SS D(d)(i)), `DISSOLVED`/Dissolved/11 (Bye-Law
  SS I), `ARCHIVED`/Archived/12, `EXPIRED`/Expired/13 (Bye-Law SS C(1)(c)). Every row carries a
  `description` citing its governing rationale — this category alone among the eight is fully
  annotated, reflecting that a shared, cross-module status vocabulary needs each value's scope
  documented up front.
- **RELATIONSHIP_TYPE (29 rows)** — by far the largest block, covering the Indian family
  structure comprehensively for the future Family module's `family_relationship` table.
  Representative rows: `SPOUSE`/Spouse/1, `FATHER`/Father/2, `MOTHER`/Mother/3 (immediate
  family, orders 1–7); `FATHER_IN_LAW`/Father-in-Law/8 through `SISTER_IN_LAW`/Sister-in-Law/13
  (in-laws); `GRANDFATHER`/Grandfather/14 through `GRANDDAUGHTER`/Granddaughter/17
  (grandparents/grandchildren); `UNCLE`/Aunt/Nephew/Niece (18–21); `COUSIN`/Cousin/22 (a single
  ungendered catch-all, unlike the gendered pairs around it); `STEP_FATHER` through
  `STEP_DAUGHTER` (23–26, step-relations); `GUARDIAN`/Guardian/27 and `WARD`/Ward/28 (a notable
  non-blood-relation pair, included because guardianship is a real family-structure concern for
  the Family module, not just biological/marital relations); and a final catch-all
  `OTHER`/Other Relative/29.
- **ORGANIZATION_TYPE (10 rows)** — the NSS Bye-Law organizational hierarchy plus preamble
  entities, replacing the retired `organization_type_master` seed's 8 rows and adding two new
  family-level types: `KENDRA`/Kendra Sangha/1, `NILACHALA_KUTIRA`/Nilachala Kutira/2,
  `SMRUTI_MANDIRA`/Smruti Mandira/3, `ANCHALIKA_SANGHA`/Anchalika Sangha/4,
  `ZILLA_SANGHA`/Zilla Sangha/5, `SAKHA_SANGHA`/Sakha Sangha/6, `SAKHA_ASANA`/Sakha Asana/7,
  `PARIBARIK_ASANA`/Paribarik Asana/8 (new — family-level Asana per Parichay Patra holder,
  Bye-Law SS C(2)(iii)), `PARIBARIK_SANGHA`/Paribarik Sangha/9 (new — family organisation
  attached to Kendra, Bye-Law Preamble), `PATHA_CHAKRA`/Patha Chakra/10.

  Sum check: 3+5+3+7+4+7+29 = **58**, matching the row count `03_validate.sh`/`.ps1` and
  `database/README.md` both expect.

---

### database/seed/01_foundation/03_id_sequence_master.sql

> **v2.0 (2026-09-12):** Two new sequences added — `PARIBARIK_ASANA` (prefix `PA`, padding 5)
> and `PARIBARIK_SANGHA` (prefix `PS`, padding 3) — for the two new `ORGANIZATION_TYPE` values
> added in `master_data`. `PARIBARIK_SANGHA`'s 3-digit padding is why
> `chk_id_sequence_padding` was loosened to `BETWEEN 2 AND 12` (see the DDL section above).

**Requirement**

Seeds the 11 business-ID sequence definitions that the application will use (once the
sequence-issuing logic is implemented) to mint permanent business identifiers for Person,
Sangha Sevi, each level of the organizational hierarchy (including the two family-level types,
Paribarik Asana and Paribarik Sangha), Family, and Document IDs.

**Line-by-line explanation**

```sql
INSERT INTO nss.id_sequence_master
    (sequence_code, sequence_name, prefix, current_value, padding_length)
VALUES (...)
```
Every row explicitly sets `current_value = 0` (no IDs issued yet) and a `padding_length` — `8`
for most rows, `10` for `PERSON`, `5` for `PARIBARIK_ASANA`, and `3` for `PARIBARIK_SANGHA`.

**Row count: 11** (all rows listed — small, fully-enumerable):

| sequence_code | sequence_name | prefix | padding_length |
|---|---|---|---|
| `PERSON` | Person Code | `P` | 10 |
| `SANGHA_SEVI` | Sangha Sevi Code | `SS` | 8 |
| `ANCHALIKA` | Anchalika Code | `ANC` | 8 |
| `ZILLA` | Zilla Code | `ZL` | 8 |
| `SAKHA` | Sakha Code | `SKH` | 8 |
| `SAKHA_ASANA` | Sakha Asana Code | `SA` | 8 |
| `PATHA_CHAKRA` | Patha Chakra Code | `PC` | 8 |
| `PARIBARIK_ASANA` | Paribarik Asana Code | `PA` | 5 |
| `PARIBARIK_SANGHA` | Paribarik Sangha Code | `PS` | 3 |
| `FAMILY` | Family Code | `F` | 8 |
| `DOCUMENT` | Document Code | `DOC` | 8 |

Notable: `PERSON` is the only sequence with a 10-digit padding (vs. 8 for most others) —
consistent with Person being expected to be the highest-cardinality entity in the system by a
wide margin (every member and every non-member family contact is a `person` row). At the other
end, `PARIBARIK_SANGHA` (3-digit) and `PARIBARIK_ASANA` (5-digit) have the narrowest padding of
any sequence — reflecting that family-level organizational units are expected to be far fewer
in number than Sakhas or persons, which is also why their addition required loosening
`chk_id_sequence_padding`'s lower bound from 4 to 2.

---

### database/seed/01_foundation/04_country.sql

**Requirement**

Seeds the 5 countries the schema currently recognizes. India is the operationally significant
one (NSS is an Odisha-based organization); the other four exist to support diaspora
members/addresses.

**Line-by-line explanation**

```sql
INSERT INTO nss.country (country_code, country_name, display_order)
VALUES ('IN', 'India', 1), ('US', 'United States', 2), ('GB', 'United Kingdom', 3),
       ('AU', 'Australia', 4), ('CA', 'Canada', 5);
```
A single plain literal `VALUES` list (no subquery needed — `country` has no parent to resolve).

**Row count: 5** (all rows listed):

| country_code | country_name | display_order |
|---|---|---|
| `IN` | India | 1 |
| `US` | United States | 2 |
| `GB` | United Kingdom | 3 |
| `AU` | Australia | 4 |
| `CA` | Canada | 5 |

---

### database/seed/01_foundation/05_state.sql

**Requirement**

Seeds every state/province/territory for all 5 seeded countries — full India coverage (needed
because NSS organizational units can, in principle, exist anywhere in India) plus full
subdivision coverage for the 4 diaspora countries.

**Line-by-line explanation**

Five blocks share the identical shape — a `CROSS JOIN` against a single-row-filtered `country`
paired with a literal `VALUES` list, same pattern as the `master_data` seed. Representative
sample (India block, showing the shape and a few rows out of 36; the other 4 country blocks are
structurally identical, just with different `WHERE c.country_code = '<CODE>'` filters and value
lists):

```sql
INSERT INTO nss.state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM nss.country c
CROSS JOIN (VALUES
    -- States (28)
    ('AP', 'Andhra Pradesh',       1),
    ('AR', 'Arunachal Pradesh',    2),
    ...
    ('OD', 'Odisha',             19),
    ...
    ('WB', 'West Bengal',        28),
    -- Union Territories (8)
    ('AN', 'Andaman and Nicobar Islands', 29),
    ...
    ('DL', 'Delhi',                       32),
    ...
    ('PY', 'Puducherry',                  36)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'IN';
```

**Row count: 112 total**, across 5 countries:

- **India (36 rows)** — all 28 states (display_order 1–28: Andhra Pradesh through West Bengal,
  alphabetical) plus all 8 union territories (display_order 29–36: Andaman and Nicobar Islands,
  Chandigarh, Dadra and Nagar Haveli and Daman and Diu, Delhi, Jammu and Kashmir, Ladakh,
  Lakshadweep, Puducherry). Example rows: `('OD', 'Odisha', 19)`, `('DL', 'Delhi', 32)`.
- **United States (51 rows)** — all 50 states (Alabama through Wyoming, alphabetical,
  display_order 1–50) plus the District of Columbia (order 51).
- **United Kingdom (4 rows)** — `ENG`/England, `SCO`/Scotland, `WLS`/Wales, `NIR`/Northern
  Ireland.
- **Australia (8 rows)** — the 6 states (`NSW`, `VIC`, `QLD`, `WA`, `SA`, `TAS`) plus 2
  territories (`ACT`, `NT`).
- **Canada (13 rows)** — the 10 provinces plus 3 territories (`NT`/Northwest Territories,
  `YT`/Yukon, `NU`/Nunavut).

Sum check: 36 + 51 + 4 + 8 + 13 = **112**, matching the expected row count in
`03_validate.sh`/`.ps1` and `database/README.md`.

Notable exception: several 2-letter `state_code` values are **reused across different
countries** — e.g. `AR` means Arkansas under `US` but Arunachal Pradesh under `IN`; `GA` means
Georgia under `US` but Goa under `IN`; `NL` means Newfoundland and Labrador under `CA` but
Nagaland under `IN`. This is not a bug — `uq_state_country_code` in the DDL scopes uniqueness to
`(country_pk, state_code)`, so cross-country reuse is explicitly permitted by design.

---

### database/seed/01_foundation/06_district.sql

**Requirement**

Seeds every district for all 28 Indian states and all 8 Indian union territories — the deepest
and most operationally relevant tier of the location hierarchy for NSS's own organizational
addresses, since NSS is Odisha-headquartered and its physical units are named/located at the
district level. Deliberately does **not** seed district-level subdivisions for the 4 diaspora
countries (the file's closing comment explains this explicitly: those subdivisions are "too
numerous and not operationally required for NSS at seed time" and would be populated at runtime
if ever needed).

**Line-by-line explanation**

36 blocks share the identical shape — one per Indian state/UT, same `CROSS JOIN` +
subquery-resolution pattern as `05_state.sql`, filtered this time on the parent `state` row
rather than `country`. Representative sample (the Odisha block in full — the largest, at 30
districts — and the smallest block, Lakshadweep's single district, showing both ends of the
size range):

```sql
-- =========================================================
-- INDIA — ODISHA (30 districts)
-- =========================================================

INSERT INTO nss.district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM nss.state s
CROSS JOIN (VALUES
    ('ANG', 'Angul',            1),
    ('BLG', 'Balangir',         2),
    ...
    ('KHD', 'Khordha',         19),
    ...
    ('PUR', 'Puri',            26),
    ...
    ('SDG', 'Sundargarh',      30)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'OD';

-- =========================================================
-- INDIA — LAKSHADWEEP (1 district)
-- =========================================================

INSERT INTO nss.district (state_pk, district_code, district_name, display_order)
SELECT s.state_pk, v.district_code, v.district_name, v.display_order
FROM nss.state s
CROSS JOIN (VALUES
    ('LKD', 'Lakshadweep', 1)
) AS v(district_code, district_name, display_order)
WHERE s.state_code = 'LD';
```

**Row count: 786**, one block per Indian state/UT (36 blocks total: 28 states + 8 UTs). Sizes
range from Odisha's 30 districts and Andhra Pradesh's/Arunachal Pradesh's 26 districts each,
down to single-district union territories. Representative rows:

- Odisha (`OD`, 30 districts, display_order 1–30): `('ANG', 'Angul', 1)`, `('CTC', 'Cuttack',
  7)`, `('KHD', 'Khordha', 19)`, `('PUR', 'Puri', 26)` — Puri and Khordha are directly relevant
  to NSS's Bhubaneswar/Puri headquarters addresses.
- Andhra Pradesh (`AP`, 26 districts): `('VIS', 'Visakhapatnam', 23)`.
- Lakshadweep (`LD`, 1 district — smallest block in the file): `('LKD', 'Lakshadweep', 1)`.

Notable exception: `district_code` values are **reused across states**, exactly parallel to the
`state_code` reuse pattern above — e.g. `KDP` is used both for Kadapa (`AP`) and Kandhamal
(`OD`); `NL` is used for Nagaland's... no — this is at the district level: uniqueness is scoped
per-state (`uq_district_state_code UNIQUE (state_pk, district_code)`), so short 3-letter codes
are freely reused across different states' district lists without collision.

---

### database/seed/01_foundation/07_system_setting.sql

**Requirement**

Seeds 4 initial application-wide configuration values. The file's own header notes these are
"illustrative defaults" — actual production values would be configured during deployment, not
hardcoded here permanently.

**Line-by-line explanation**

```sql
INSERT INTO nss.system_setting (setting_key, setting_value, description, data_type)
VALUES (...)
```

**Row count: 4** (all rows listed):

| setting_key | setting_value | data_type |
|---|---|---|
| `CURRENT_MEMBERSHIP_YEAR` | `2026-2027` | STRING |
| `DEFAULT_COUNTRY` | `IN` | STRING |
| `PASSWORD_EXPIRY_DAYS` | `90` | INTEGER |
| `MAX_LOGIN_ATTEMPTS` | `5` | INTEGER |

Notable: `PASSWORD_EXPIRY_DAYS` and `MAX_LOGIN_ATTEMPTS` are Authentication-module concerns
seeded here in Foundation ahead of the Authentication module's own tables being built — the
generic `system_setting` table is deliberately module-agnostic, so it can hold configuration for
not-yet-implemented modules without needing schema changes later.

---

### database/seed/01_foundation/08_postal_code.sql

**Requirement**

Seeds the handful of postal codes needed by the Organization seed data (`03_organization.sql`
resolves `751022` and `752001` via subquery; `753001` backs Tier 4 verification). The file's own
header is explicit that this is a "minimal bootstrap set" — the full all-India load lives in
`08b_postal_code_bulk.sql`. Under the Simplified Geography Model (2026-10-02) these same PINs
are also present in the bulk load, so this file is effectively a no-op safety net, kept so the
bulk file is not a hard prerequisite.

**Line-by-line explanation**

```sql
-- Bhubaneswar — Kendra (Satsikshya Mandir, Unit-9)
INSERT INTO nss.postal_code (state_pk, postal_code)
SELECT s.state_pk, '751022'
FROM nss.country c
JOIN nss.state s ON s.country_pk = c.country_pk
WHERE c.country_code = 'IN'
  AND s.state_code = 'OD'
ON CONFLICT (postal_code) DO UPDATE SET
    state_pk = EXCLUDED.state_pk;

-- Puri — Nilachala Kutira, Smruti Mandira (Swargadwar area)
INSERT INTO nss.postal_code (state_pk, postal_code)
SELECT s.state_pk, '752001'
FROM nss.country c
JOIN nss.state s ON s.country_pk = c.country_pk
WHERE c.country_code = 'IN'
  AND s.state_code = 'OD'
ON CONFLICT (postal_code) DO UPDATE SET
    state_pk = EXCLUDED.state_pk;
```

One statement per PIN, using an explicit `JOIN` (rather than the `CROSS JOIN`-against-VALUES
pattern used elsewhere) since each statement inserts a single literal row. Note that only
`state_pk` is inserted — `nss.postal_code` no longer has a `country_pk` or `post_office_name`
column, so the `nss.country` join survives purely as a *filter* (`country_code = 'IN'`) to
disambiguate the Odisha state row, not to supply a value. Each statement ends in `ON CONFLICT
(postal_code) DO UPDATE SET state_pk = EXCLUDED.state_pk` — the global `UNIQUE (postal_code)`
key makes the upsert idempotent and lets this file run before or after the bulk load in either
order.

**Row count: 3** (all rows listed):

| postal_code | Context |
|---|---|
| `751022` | Bhubaneswar — Kendra (Satsikshya Mandir, Unit-9) |
| `752001` | Puri — Nilachala Kutira / Smruti Mandira (Swargadwar area) |
| `753001` | Cuttack — Tier 4 verification (second Sakha location) |

All three rows resolve to `state_code = 'OD'` (Odisha) — every PIN seeded by *this* file is in
Odisha, matching where NSS's seeded organizations physically are; their country is reached
through `state.country_pk` rather than stored on the row.

---

### database/ddl/02_organization/01_organization_type_master.sql

> **RETIRED — replaced by Foundation `master_data` (category `ORGANIZATION_TYPE`), 2026-09-12.**
> This file no longer exists in the working tree (deleted as part of the org-to-master-data
> migration on `feature/migration-org-to-master-data`). Organization type values now live as
> `nss.master_data` rows under the shared `ORGANIZATION_TYPE` category (seeded in
> `database/seed/01_foundation/02_master_data.sql`, 10 values), and `organization` references
> them via `organization_type_master_data_pk` → `nss.master_data(master_data_pk)` instead of a
> dedicated FK. The DDL below is preserved as it existed at time of retirement, for readers
> encountering it via `git blame`/history.

**Requirement**

Defines `nss.organization_type_master` — the fixed catalogue of organizational unit types
(Kendra, Anchalika, Zilla, Sakha, etc.). Depth 0. Without it, `organization` (Depth 3) has no
type to classify itself by, and there would be no frozen, database-backed answer to "what kinds
of organizational units exist in NSS's structure."

**Line-by-line explanation**

```sql
CREATE TABLE nss.organization_type_master
(
    organization_type_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_type_code VARCHAR(30) NOT NULL,

    organization_type_name VARCHAR(100) NOT NULL,

    description VARCHAR(500) NULL,

    sort_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `organization_type_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`;
`organization_type_code VARCHAR(30) NOT NULL`; `organization_type_name VARCHAR(100) NOT NULL`;
`description VARCHAR(500) NULL` — note this is a bounded `VARCHAR(500)`, not `TEXT`, unlike most
other `description` columns in the schema; `sort_order INTEGER NOT NULL DEFAULT 0`; standard
four-column audit block (`created_at`/`updated_at`/`deleted_at`/`is_active`).

```sql
    CONSTRAINT uq_organization_type_code
        UNIQUE (organization_type_code),

    CONSTRAINT uq_organization_type_name
        UNIQUE (organization_type_name),

    CONSTRAINT chk_organization_type_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_organization_type_active
    ON nss.organization_type_master (is_active);
```

Constraints: `uq_organization_type_code UNIQUE (organization_type_code)`,
`uq_organization_type_name UNIQUE (organization_type_name)`, `chk_organization_type_soft_delete`
standard invariant.

Indexes: only `idx_organization_type_active (is_active)` — no code-lookup index, unlike most
other master tables in this document (a minor asymmetry, since `organization_type_code` is a
`UNIQUE` column and Postgres does create an implicit index for the unique constraint itself,
which likely explains why a redundant explicit index wasn't added).

---

### database/ddl/02_organization/02_organization_status_master.sql

> **RETIRED — replaced by Foundation `master_data` (category `STATUS`), 2026-09-12.** This file
> no longer exists in the working tree (deleted as part of the org-to-master-data migration on
> `feature/migration-org-to-master-data`). Organization lifecycle status is no longer
> organization-specific: it now uses the unified ERP-wide `STATUS` category in `nss.master_data`
> (seeded in `database/seed/01_foundation/02_master_data.sql`, 13 values shared across
> organizations, memberships, governance, etc.), and `organization` references it via
> `status_master_data_pk` → `nss.master_data(master_data_pk)` instead of a dedicated FK. The DDL
> below is preserved as it existed at time of retirement, for readers encountering it via
> `git blame`/history.

**Requirement**

Defines `nss.organization_status_master` — the fixed catalogue of organizational lifecycle
statuses (Proposed → Approved → Active → Inactive/Suspended → Archived). Depth 0, sibling to
`organization_type_master`. Without it, `organization` has no way to express current lifecycle
state.

**Line-by-line explanation**

```sql
CREATE TABLE nss.organization_status_master
(
    organization_status_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_status_code VARCHAR(30) NOT NULL,

    organization_status_name VARCHAR(100) NOT NULL,

    description VARCHAR(500) NULL,

    sort_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Identical column shape to `organization_type_master`: `organization_status_pk UUID PRIMARY KEY
DEFAULT gen_random_uuid()`; `organization_status_code VARCHAR(30) NOT NULL`;
`organization_status_name VARCHAR(100) NOT NULL`; `description VARCHAR(500) NULL`; `sort_order
INTEGER NOT NULL DEFAULT 0`; standard four-column audit block.

```sql
    CONSTRAINT uq_organization_status_code
        UNIQUE (organization_status_code),

    CONSTRAINT uq_organization_status_name
        UNIQUE (organization_status_name),

    CONSTRAINT chk_organization_status_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_organization_status_active
    ON nss.organization_status_master (is_active);
```

Constraints: `uq_organization_status_code UNIQUE (organization_status_code)`,
`uq_organization_status_name UNIQUE (organization_status_name)`,
`chk_organization_status_soft_delete` standard invariant.

Indexes: `idx_organization_status_active (is_active)` only — same pattern as the type master.

---

### database/ddl/02_organization/03_organization.sql

> **v2.0 (2026-09-12):** `organization_type_pk` renamed to `organization_type_master_data_pk`
> and `organization_status_pk` renamed to `status_master_data_pk`, both now FKs into
> `nss.master_data(master_data_pk)` instead of the retired `organization_type_master`/
> `organization_status_master` tables. See the RETIRED notices above for the tables this
> replaces.

**Requirement**

Defines `nss.organization` — every physical/administrative organizational unit in NSS's
hierarchy (Kendra, Anchalika Sangha, Zilla Sangha, Sakha Sangha, Sakha Asana, Patha Chakra,
Nilachala Kutira, Smruti Mandira), self-referencing to express parent/child structure. Depth 1
(depends on Foundation's `master_data` for type/status classification, and the location tables
`country`/`state`/`district`/`city_village`/`postal_code`, plus itself via the self-referencing
FK). Without this table, NSS's organizational structure — the entire reason the "Organization"
module exists — has no physical representation at all.

**Line-by-line explanation**

Identity, classification, and hierarchy columns:

```sql
CREATE TABLE nss.organization
(
    organization_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- Business identifier (system-generated for multi-instance
    -- org types; NULL for unique organizations identified by
    -- organization_code alone)
    organization_id VARCHAR(20) NULL,

    organization_name VARCHAR(200) NOT NULL,

    -- Classification (FK → master_data, category ORGANIZATION_TYPE)
    organization_type_master_data_pk UUID NOT NULL,

    -- Current lifecycle status (FK → master_data, category STATUS)
    status_master_data_pk UUID NOT NULL,

    -- Hierarchy: immediate parent (NULL = apex)
    parent_organization_pk UUID NULL,

    -- Organization short code (3-5 chars, unique)
    organization_code VARCHAR(10) NULL,
```

- `organization_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `organization_id VARCHAR(20) NULL` — a *system-generated business identifier*, used only for
  multi-instance organization types (e.g. many Sakhas each need their own sequential ID via
  `id_sequence_master`'s `SAKHA` sequence); left `NULL` for the three unique, one-off
  organizations (Kendra, Nilachala Kutira, Smruti Mandira) that are identified by
  `organization_code` alone.
- `organization_name VARCHAR(200) NOT NULL`.
- `organization_type_master_data_pk UUID NOT NULL` — FK into Foundation's `nss.master_data`,
  category `ORGANIZATION_TYPE`; classification. Renamed from the pre-migration
  `organization_type_pk` FK to the now-retired `organization_type_master`.
- `status_master_data_pk UUID NOT NULL` — FK into Foundation's `nss.master_data`, category
  `STATUS` (the unified ERP-wide lifecycle status, shared across modules); current lifecycle
  state. Renamed from the pre-migration `organization_status_pk` FK to the now-retired
  `organization_status_master`.
- `parent_organization_pk UUID NULL` — self-referencing FK; `NULL` means this organization is
  an apex node (has no parent).
- `organization_code VARCHAR(10) NULL` — a short, hand-assigned unique code (e.g. `KEN`, `NKT`,
  `SMR` in the seed data below); nullable, but unique when present.

Inline address/location and coordinate columns:

```sql
    -- Inline address (current address, v1 design)
    address_line_1 VARCHAR(200) NULL,

    address_line_2 VARCHAR(200) NULL,

    district_pk UUID NULL,

    state_pk UUID NULL,

    country_pk UUID NULL,

    city_village_pk UUID NULL,

    postal_code_pk UUID NULL,

    -- Physical coordinates of this organization
    latitude NUMERIC(10,7) NULL,

    longitude NUMERIC(10,7) NULL,
```

- `address_line_1 VARCHAR(200) NULL`, `address_line_2 VARCHAR(200) NULL` — inline address
  fields; the file's header note explicitly records the frozen design decision that
  Organization does **not** get a separate `organization_address` table (unlike Person's
  prototype, which does have `person_address`).
- `district_pk UUID NULL`, `state_pk UUID NULL`, `country_pk UUID NULL`, `city_village_pk UUID
  NULL`, `postal_code_pk UUID NULL` — five separate, independently nullable location FKs (not a
  single FK to a combined location-map row) — an organization can specify as much or as little
  of its address hierarchy as is known.
- `latitude NUMERIC(10,7) NULL`, `longitude NUMERIC(10,7) NULL` — physical coordinates, bounded
  by CHECK constraints below.

Audit block, constraints, and indexes:

```sql
    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- Unique constraints
    CONSTRAINT uq_organization_id
        UNIQUE (organization_id),

    CONSTRAINT uq_organization_code
        UNIQUE (organization_code),

    -- Foreign keys: classification + lifecycle (now via master_data)
    CONSTRAINT fk_organization_type
        FOREIGN KEY (organization_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_organization_status
        FOREIGN KEY (status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    -- Self-referencing FK: hierarchy
    CONSTRAINT fk_organization_parent
        FOREIGN KEY (parent_organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- Location FKs (Foundation tables)
    CONSTRAINT fk_organization_district
        FOREIGN KEY (district_pk)
        REFERENCES nss.district (district_pk),

    CONSTRAINT fk_organization_state
        FOREIGN KEY (state_pk)
        REFERENCES nss.state (state_pk),

    CONSTRAINT fk_organization_country
        FOREIGN KEY (country_pk)
        REFERENCES nss.country (country_pk),

    CONSTRAINT fk_organization_city_village
        FOREIGN KEY (city_village_pk)
        REFERENCES nss.city_village (city_village_pk),

    CONSTRAINT fk_organization_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    -- Coordinate range validation
    CONSTRAINT chk_organization_latitude
        CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),

    CONSTRAINT chk_organization_longitude
        CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),

    -- Soft-delete consistency
    CONSTRAINT chk_organization_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Indexes
CREATE INDEX idx_organization_type
    ON nss.organization (organization_type_master_data_pk);

CREATE INDEX idx_organization_status
    ON nss.organization (status_master_data_pk);

CREATE INDEX idx_organization_parent
    ON nss.organization (parent_organization_pk);

CREATE INDEX idx_organization_country
    ON nss.organization (country_pk);

CREATE INDEX idx_organization_state
    ON nss.organization (state_pk);

CREATE INDEX idx_organization_district
    ON nss.organization (district_pk);

CREATE INDEX idx_organization_city_village
    ON nss.organization (city_village_pk);

CREATE INDEX idx_organization_postal_code
    ON nss.organization (postal_code_pk);

CREATE INDEX idx_organization_active
    ON nss.organization (is_active);

CREATE INDEX idx_organization_name
    ON nss.organization USING gin (organization_name gin_trgm_ops);
```

- Standard four-column audit block (`created_at`/`updated_at`/`deleted_at`/`is_active`) — no
  actor columns, consistent with the rest of Organization/Foundation.
- `uq_organization_id UNIQUE (organization_id)` and `uq_organization_code UNIQUE
  (organization_code)` — both unique when non-`NULL` (multiple `NULL`s are permitted by
  standard SQL unique-constraint semantics, which is exactly what allows all three seeded
  unique organizations to share `organization_id = NULL`).
- `fk_organization_type FOREIGN KEY (organization_type_master_data_pk) REFERENCES
  nss.master_data (master_data_pk)` — points at Foundation's shared master-data table rather
  than a dedicated `organization_type_master`; the application layer is responsible for
  constraining which `master_data` rows are valid here (i.e. only rows under the
  `ORGANIZATION_TYPE` category) since the FK itself cannot express a category filter.
- `fk_organization_status FOREIGN KEY (status_master_data_pk) REFERENCES nss.master_data
  (master_data_pk)` — same pattern, pointed at the unified `STATUS` category shared across
  modules rather than a dedicated `organization_status_master`.
- `fk_organization_parent FOREIGN KEY (parent_organization_pk) REFERENCES nss.organization
  (organization_pk)` — the self-referencing FK; the file's header explains this is only
  possible in the base `CREATE TABLE` (rather than needing a later `ALTER TABLE`, as with
  Bootstrap's Pass-2 actor FKs) because the table already exists by the time this constraint is
  declared, even though it's declared inline in the same statement that creates the table.
- `fk_organization_district`, `fk_organization_state`, `fk_organization_country`,
  `fk_organization_city_village`, `fk_organization_postal_code` — five FKs to the Foundation
  location tables, each referencing the location table's own PK.
- `chk_organization_latitude CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <=
  90))` and `chk_organization_longitude CHECK (longitude IS NULL OR (longitude >= -180 AND
  longitude <= 180))` — standard geographic coordinate range validation, each independently
  optional.
- `chk_organization_soft_delete` — standard invariant.

The file's header also documents a design decision that is explicitly **not** expressed as a
column: `hierarchical_level` is not stored — an organization's "level" is fully derived from
`organization_type_master_data_pk` (which type it is) combined with walking the
`parent_organization_pk` chain, rather than being cached as a denormalized integer.

Indexes: `idx_organization_type (organization_type_master_data_pk)`, `idx_organization_status
(status_master_data_pk)`, `idx_organization_parent (parent_organization_pk)`,
`idx_organization_country (country_pk)`, `idx_organization_state (state_pk)`,
`idx_organization_district (district_pk)`, `idx_organization_city_village (city_village_pk)`,
`idx_organization_postal_code (postal_code_pk)`, `idx_organization_active (is_active)`, and
`idx_organization_name USING gin (organization_name gin_trgm_ops)` (fuzzy search) — every single
FK column gets its own index, reflecting how central hierarchy/location traversal is expected to
be for this table.

---

### database/seed/02_organization/01_organization_type_master.sql

> **RETIRED — replaced by Foundation `master_data` seed (category `ORGANIZATION_TYPE`),
> 2026-09-12.** This file no longer exists. The 8 rows it seeded are superseded by the 10-row
> `ORGANIZATION_TYPE` block in `database/seed/01_foundation/02_master_data.sql` (adds
> `PARIBARIK_ASANA` and `PARIBARIK_SANGHA`). The content below is preserved as it existed at
> time of retirement, for readers encountering it via `git blame`/history.

**Requirement**

Seeds the 8 frozen organization types that every `organization` row must classify itself under.

**Line-by-line explanation**

```sql
INSERT INTO nss.organization_type_master
    (organization_type_code, organization_type_name, description, sort_order)
VALUES (...)
```

**Row count: 8** (all rows listed):

| organization_type_code | organization_type_name | description | sort_order |
|---|---|---|---|
| `KENDRA` | Kendra Sangha | Central Body — apex organization | 1 |
| `NILACHALA_KUTIRA` | Nilachala Kutira | Eternal Abode - Puri | 2 |
| `SMRUTI_MANDIRA` | Smruti Mandira | Nigamananda Smruti Mandir | 3 |
| `ANCHALIKA_SANGHA` | Anchalika Sangha | Administrative unit — intermediate organizational level | 4 |
| `ZILLA_SANGHA` | Zilla Sangha | Administrative unit — intermediate organizational level | 5 |
| `SAKHA_SANGHA` | Sakha Sangha | Physical Sangha location — branch with own building | 6 |
| `SAKHA_ASANA` | Sakha Asana | Approved Sakha without own building | 7 |
| `PATHA_CHAKRA` | Patha Chakra | Study Circle | 8 |

Notable: three of the eight types (`KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`) are
**singleton** types — exactly one organization of each will ever exist (seeded in
`03_organization.sql` below) — while the other five (`ANCHALIKA_SANGHA` through
`PATHA_CHAKRA`) are multi-instance types intended for many future organization rows each, which
is why `organization.organization_id` (the sequence-generated business ID) only makes sense for
those five.

---

### database/seed/02_organization/02_organization_status_master.sql

> **RETIRED — replaced by Foundation `master_data` seed (unified category `STATUS`),
> 2026-09-12.** This file no longer exists. The 6 rows it seeded are superseded by the 13-row
> `STATUS` block in `database/seed/01_foundation/02_master_data.sql`, which is shared across all
> ERP modules rather than owned by Organization alone. The content below is preserved as it
> existed at time of retirement, for readers encountering it via `git blame`/history.

**Requirement**

Seeds the 6 frozen organizational lifecycle statuses every `organization` row's
`organization_status_pk` must reference.

**Line-by-line explanation**

```sql
INSERT INTO nss.organization_status_master
    (organization_status_code, organization_status_name, description, sort_order)
VALUES (...)
```

**Row count: 6** (all rows listed):

| organization_status_code | organization_status_name | sort_order |
|---|---|---|
| `PROPOSED` | Proposed | 1 |
| `APPROVED` | Approved | 2 |
| `ACTIVE` | Active | 3 |
| `INACTIVE` | Inactive | 4 |
| `SUSPENDED` | Suspended | 5 |
| `ARCHIVED` | Archived | 6 |

The six statuses form a linear lifecycle progression from proposal through governance approval
to operation, with `INACTIVE`/`SUSPENDED` as two distinct non-operational states (temporary vs.
governance-imposed) and `ARCHIVED` as the permanent terminal state — consistent with the
project's "History Never Deleted" principle (an archived organization's row is retained
forever, never hard-deleted).

---

### database/seed/02_organization/03_organization.sql

> **v2.0 (2026-09-12):** Lookups switched from `CROSS JOIN nss.organization_type_master` /
> `nss.organization_status_master` to `JOIN nss.master_data ... JOIN nss.master_category ...`
> filtered by `category_code`, matching the renamed `organization_type_master_data_pk` /
> `status_master_data_pk` columns on `organization`.

**Requirement**

Seeds the three actual, named, unique organizations that exist in NSS's structure today: the
apex Kendra Sangha itself, Nilachala Kutira (Puri), and Smruti Mandira (the Nigamananda
memorial temple). These are the only organization rows that exist prior to any live
administrative data entry — every other Anchalika/Zilla/Sakha/Patha Chakra will be created at
runtime through the (not-yet-built) Organization module UI.

**Line-by-line explanation**

Representative block (Kendra Sangha — the other two blocks, Nilachala Kutira and Smruti
Mandira, follow the identical shape with different literal values and `WHERE` filters):

```sql
-- -------------------------------------------------
-- Kendra Sangha (apex governing body)
-- -------------------------------------------------

INSERT INTO nss.organization
    (organization_name, organization_type_master_data_pk,
     status_master_data_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk,
     phone_number, mobile_number)
SELECT
    'Nilachala Saraswata Sangha',
    ot.master_data_pk,
    os.master_data_pk,
    NULL,
    'KEN',
    'Satsikshya Mandir, A/4, Unit-9',
    'Bhubaneswar',
    pc.postal_code_pk,
    c.country_pk,
    '+91-674-2390055',
    '+91-9238106823'
FROM nss.master_data ot
JOIN nss.master_category mc_type
     ON mc_type.master_category_pk = ot.master_category_pk
CROSS JOIN nss.master_data os
JOIN nss.master_category mc_status
     ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.country c
CROSS JOIN nss.postal_code pc
JOIN nss.state s ON s.state_pk = pc.state_pk
WHERE mc_type.category_code = 'ORGANIZATION_TYPE'
  AND ot.value_code = 'KENDRA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '751022'
  AND s.country_pk = c.country_pk;
```

Rather than the pre-migration four-way `CROSS JOIN` across two dedicated lookup tables plus
`country`/`postal_code`, the type and status lookups are now each a `JOIN nss.master_data ...
JOIN nss.master_category ...` pair — `master_data` gives the row's `master_data_pk` and
`value_code`, `master_category` supplies the `category_code` needed to disambiguate which
shared category (`ORGANIZATION_TYPE` vs `STATUS`) the `value_code` filter applies to (since
`master_data.value_code` alone is not globally unique across categories). The `ot`/`os` aliases
for `master_data` and `mc_type`/`mc_status` aliases for `master_category` are still combined
with `country`/`postal_code` via `CROSS JOIN`, each narrowed to exactly one row by the `WHERE`
clause, so the `SELECT` resolves to exactly one row of PKs to insert. The one non-`CROSS` join
in the geography half is `JOIN nss.state s ON s.state_pk = pc.state_pk`: since the Simplified
Geography Model (2026-10-02) dropped `postal_code.country_pk`, the sanity check that the chosen
PIN really belongs to the chosen country has to hop through the PIN's state, hence `s.country_pk
= c.country_pk` rather than the former `pc.country_pk = c.country_pk`. All three blocks
explicitly pass `parent_organization_pk = NULL` — the file's header confirms all three are peers
(no parent/child relationship among them) and all three are seeded with `value_code = 'ACTIVE'`
(under the `STATUS` category) from the start. `city_village_pk` is left unset (omitted from the
column list, so it defaults to `NULL`) because, per the header comment, Foundation's
`city_village` seed data doesn't exist yet.

**Row count: 3** (all rows listed):

| organization_name | type | organization_code | address_line_1 | address_line_2 | postal_code |
|---|---|---|---|---|---|
| Nilachala Saraswata Sangha | KENDRA | `KEN` | Satsikshya Mandir, A/4, Unit-9 | Bhubaneswar | `751022` |
| Nilachala Kutira | NILACHALA_KUTIRA | `NKT` | Puri | `NULL` | `752001` |
| Sri Shri Nigamananda Smruti Mandir | SMRUTI_MANDIRA | `SMR` | Swargadwar Rd, Bali Sahi | Puri | `752001` |

Notable: the Kendra Sangha row's `organization_name` ("Nilachala Saraswata Sangha") is the
*full organizational name of NSS itself*, not literally the word "Kendra" — the apex
organization row represents the whole Sangha's central body, distinct from its
`organization_type_code = 'KENDRA'` classification. The file's own header also explicitly notes
all seeded addresses are editable at runtime — these are initial values only, not frozen facts.

---

### database/ddl/03_person/01_person_master_tables.sql

> **SUPERSEDED PROTOTYPE — not executed by `02_build.sh`/`02_build.ps1`, kept for reference
> only.** Uses dedicated per-domain master tables instead of the generic
> `master_category`/`master_data` pattern that Foundation actually implements — the values this
> file's tables would hold (gender, marital status, address type) are already covered by
> `master_data` rows seeded under the `GENDER`, `MARITAL_STATUS`, and `ADDRESS_TYPE` categories.
> This duplication is precisely why the prototype was superseded.

**Requirement (as originally written)**

Defines three small per-domain lookup tables (`gender_master`, `marital_status_master`,
`address_type_master`) intended to back the prototype `person` table's `gender_pk` and
`marital_status_pk` FKs, and the prototype `person_address` table's `address_type_pk` FK.

**Line-by-line explanation**

All three tables share an identical shape and a notable difference from every Foundation table:
none of the `CREATE TABLE` statements are schema-qualified (`CREATE TABLE gender_master`, not
`CREATE TABLE nss.gender_master`) — they would land in whatever the connecting session's default
schema is, not explicitly `nss`, unlike every other table in this document.

```sql
CREATE TABLE gender_master
(
gender_pk UUID PRIMARY KEY
DEFAULT gen_random_uuid(),


gender_code VARCHAR(20) NOT NULL,

gender_name VARCHAR(50) NOT NULL,

display_order INTEGER NOT NULL,

created_at TIMESTAMPTZ NOT NULL
    DEFAULT CURRENT_TIMESTAMP,

is_active BOOLEAN NOT NULL
    DEFAULT TRUE,

CONSTRAINT uq_gender_master_code
    UNIQUE (gender_code),

CONSTRAINT uq_gender_master_name
    UNIQUE (gender_name)


);

CREATE INDEX idx_gender_master_active
ON gender_master (is_active);
```

- **`gender_master`**: `gender_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `gender_code
  VARCHAR(20) NOT NULL`; `gender_name VARCHAR(50) NOT NULL`; `display_order INTEGER NOT NULL`
  — **no `DEFAULT`** on `display_order` here, unlike every Foundation equivalent (`DEFAULT 0`),
  meaning every insert must supply it explicitly or fail; `created_at TIMESTAMPTZ NOT NULL
  DEFAULT CURRENT_TIMESTAMP`; `is_active BOOLEAN NOT NULL DEFAULT TRUE`. Constraints:
  `uq_gender_master_code UNIQUE (gender_code)`, `uq_gender_master_name UNIQUE (gender_name)`.
  Notably **no `updated_at`, no `deleted_at`, and no soft-delete CHECK constraint** — `is_active`
  exists but nothing enforces that `is_active = FALSE` correlates with any deletion timestamp,
  because there is no deletion timestamp column at all. Index: `idx_gender_master_active
  (is_active)`.

```sql
CREATE TABLE marital_status_master
(
marital_status_pk UUID PRIMARY KEY
DEFAULT gen_random_uuid(),


marital_status_code VARCHAR(30) NOT NULL,

marital_status_name VARCHAR(100) NOT NULL,

display_order INTEGER NOT NULL,

created_at TIMESTAMPTZ NOT NULL
    DEFAULT CURRENT_TIMESTAMP,

is_active BOOLEAN NOT NULL
    DEFAULT TRUE,

CONSTRAINT uq_marital_status_code
    UNIQUE (marital_status_code),

CONSTRAINT uq_marital_status_name
    UNIQUE (marital_status_name)


);

CREATE INDEX idx_marital_status_active
ON marital_status_master (is_active);
```

- **`marital_status_master`**: identical shape — `marital_status_pk`, `marital_status_code
  VARCHAR(30) NOT NULL`, `marital_status_name VARCHAR(100) NOT NULL`, `display_order INTEGER NOT
  NULL` (no default), `created_at`, `is_active`; unique constraints on both code and name; same
  missing-soft-delete-tracking gap; index on `is_active`.

```sql
CREATE TABLE address_type_master
(
address_type_pk UUID PRIMARY KEY
DEFAULT gen_random_uuid(),


address_type_code VARCHAR(30) NOT NULL,

address_type_name VARCHAR(100) NOT NULL,

display_order INTEGER NOT NULL,

created_at TIMESTAMPTZ NOT NULL
    DEFAULT CURRENT_TIMESTAMP,

is_active BOOLEAN NOT NULL
    DEFAULT TRUE,

CONSTRAINT uq_address_type_code
    UNIQUE (address_type_code),

CONSTRAINT uq_address_type_name
    UNIQUE (address_type_name)


);

CREATE INDEX idx_address_type_active
ON address_type_master (is_active);
```

- **`address_type_master`**: identical shape again — `address_type_pk`, `address_type_code
  VARCHAR(30) NOT NULL`, `address_type_name VARCHAR(100) NOT NULL`, `display_order INTEGER NOT
  NULL` (no default), `created_at`, `is_active`; unique constraints on both; same gap; index on
  `is_active`.

---

### database/ddl/03_person/02_person.sql

> **SUPERSEDED PROTOTYPE — not executed by `02_build.sh`/`02_build.ps1`, kept for reference
> only.** Will be rewritten against the frozen `master_category`/`master_data` pattern (see
> `feature/person-ddl` and `database/README.md` → "Superseded Artifacts").

**Requirement (as originally written)**

Defines the prototype `person` table — the core identity record every human in the system
(member or not) would attach to, per the project's frozen "Person ≠ Member" principle.

**Line-by-line explanation**

```sql
CREATE TABLE person
(
    person_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    person_code VARCHAR(20) NOT NULL,

    first_name VARCHAR(100) NOT NULL,

    middle_name VARCHAR(100) NULL,

    last_name VARCHAR(100) NULL,

    gender_pk UUID NOT NULL,

    date_of_birth DATE NULL,

    country_phone_code VARCHAR(10) NULL,

    mobile_number VARCHAR(20) NULL,

    email VARCHAR(255) NULL,

    marital_status_pk UUID NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `person_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `person_code VARCHAR(20) NOT
NULL` — intended to be issued from the `PERSON` row in `id_sequence_master`, though nothing in
this DDL enforces that link (it's plain `VARCHAR`, populated by application logic); `first_name
VARCHAR(100) NOT NULL`; `middle_name VARCHAR(100) NULL`; `last_name VARCHAR(100) NULL` —
nullable, allowing single-name persons; `gender_pk UUID NOT NULL` — FK, required; `date_of_birth
DATE NULL`; `country_phone_code VARCHAR(10) NULL`; `mobile_number VARCHAR(20) NULL`; `email
VARCHAR(255) NULL`; `marital_status_pk UUID NULL` — FK, optional; `remarks TEXT NULL`;
`created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`, `updated_at TIMESTAMPTZ NULL`,
`deleted_at TIMESTAMPTZ NULL`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

```sql
    CONSTRAINT uq_person_code
        UNIQUE (person_code),

    CONSTRAINT uq_person_mobile
        UNIQUE
        (
            country_phone_code,
            mobile_number
        ),

    CONSTRAINT fk_person_gender
        FOREIGN KEY (gender_pk)
        REFERENCES gender_master(gender_pk),

    CONSTRAINT fk_person_marital_status
        FOREIGN KEY (marital_status_pk)
        REFERENCES marital_status_master(marital_status_pk),

    CONSTRAINT chk_person_contact_required
        CHECK
        (
            mobile_number IS NOT NULL
            OR
            email IS NOT NULL
        ),

    CONSTRAINT chk_person_mobile_pair
        CHECK
        (
            (
                country_phone_code IS NULL
                AND mobile_number IS NULL
            )
            OR
            (
                country_phone_code IS NOT NULL
                AND mobile_number IS NOT NULL
            )
        )
);

CREATE INDEX idx_person_code
    ON person(person_code);

CREATE INDEX idx_person_first_name
    ON person(first_name);

CREATE INDEX idx_person_last_name
    ON person(last_name);

CREATE INDEX idx_person_mobile
    ON person(country_phone_code, mobile_number);

CREATE INDEX idx_person_email
    ON person(email);

CREATE INDEX idx_person_gender
    ON person(gender_pk);

CREATE INDEX idx_person_marital_status
    ON person(marital_status_pk);

CREATE INDEX idx_person_is_active
    ON person(is_active);
```

Constraints:
- `uq_person_code UNIQUE (person_code)`.
- `uq_person_mobile UNIQUE (country_phone_code, mobile_number)` — a composite uniqueness rule
  (the same raw mobile number is allowed to recur across different country codes, but not
  within the same country code).
- `fk_person_gender FOREIGN KEY (gender_pk) REFERENCES gender_master(gender_pk)` and
  `fk_person_marital_status FOREIGN KEY (marital_status_pk) REFERENCES
  marital_status_master(marital_status_pk)` — both unqualified references (no `nss.` prefix,
  consistent with this prototype's schema-unqualified style throughout).
- `chk_person_contact_required CHECK (mobile_number IS NOT NULL OR email IS NOT NULL)` — at
  least one contact channel is mandatory.
- `chk_person_mobile_pair CHECK ((country_phone_code IS NULL AND mobile_number IS NULL) OR
  (country_phone_code IS NOT NULL AND mobile_number IS NOT NULL))` — the phone code and number
  must be supplied together or not at all; you can't have one without the other.

Notably, unlike every Foundation table, there is **no soft-delete CHECK constraint** here even
though `deleted_at` and `is_active` both exist as columns — the invariant that other tables
enforce mechanically is simply absent in this prototype.

Indexes: `idx_person_code (person_code)`, `idx_person_first_name (first_name)`,
`idx_person_last_name (last_name)`, `idx_person_mobile (country_phone_code, mobile_number)`,
`idx_person_email (email)`, `idx_person_gender (gender_pk)`, `idx_person_marital_status
(marital_status_pk)`, `idx_person_is_active (is_active)`.

---

### database/ddl/03_person/03_person_address.sql

> **SUPERSEDED PROTOTYPE — not executed by `02_build.sh`/`02_build.ps1`, kept for reference
> only.**

**Requirement (as originally written)**

Defines the prototype `person_address` table — one or more addresses per person, each typed
(permanent/current/official) and located via the Foundation `city_village_postal_code_map`
table, with exactly one address per person flaggable as primary.

**Line-by-line explanation**

```sql
CREATE TABLE person_address
(
    person_address_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    person_pk UUID NOT NULL,

    address_type_pk UUID NOT NULL,

    address_line_1 VARCHAR(255) NOT NULL,

    address_line_2 VARCHAR(255) NULL,

    landmark VARCHAR(255) NULL,

    city_village_postal_code_map_pk UUID NOT NULL,

    is_primary BOOLEAN NOT NULL
        DEFAULT FALSE,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,
```

Columns: `person_address_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `person_pk UUID NOT
NULL` — FK to `person`; `address_type_pk UUID NOT NULL` — FK to `address_type_master`;
`address_line_1 VARCHAR(255) NOT NULL`; `address_line_2 VARCHAR(255) NULL`; `landmark
VARCHAR(255) NULL`; `city_village_postal_code_map_pk UUID NOT NULL` — FK, and notably references
the Foundation **map** table directly (not `city_village_pk` and `postal_code_pk` as two
separate FKs) — one address row pins down both the locality and the specific PIN code
simultaneously via a single join-table row; `is_primary BOOLEAN NOT NULL DEFAULT FALSE`;
`remarks TEXT NULL`; standard four-column audit block (`created_at`/`updated_at`/`deleted_at`/
`is_active`).

```sql
    CONSTRAINT fk_person_address_person
        FOREIGN KEY (person_pk)
        REFERENCES person(person_pk),

    CONSTRAINT fk_person_address_type
        FOREIGN KEY (address_type_pk)
        REFERENCES address_type_master(address_type_pk),

    CONSTRAINT fk_person_address_location
        FOREIGN KEY (city_village_postal_code_map_pk)
        REFERENCES city_village_postal_code_map(city_village_postal_code_map_pk)
);

-- =====================================================
-- Indexes
-- =====================================================

CREATE INDEX idx_person_address_person
    ON person_address(person_pk);

CREATE INDEX idx_person_address_type
    ON person_address(address_type_pk);

CREATE INDEX idx_person_address_location
    ON person_address(city_village_postal_code_map_pk);

CREATE INDEX idx_person_address_active
    ON person_address(is_active);

-- =====================================================
-- Only One Primary Address Per Person
-- =====================================================

CREATE UNIQUE INDEX uq_person_primary_address
ON person_address(person_pk)
WHERE is_primary = TRUE;
```

Constraints: `fk_person_address_person FOREIGN KEY (person_pk) REFERENCES person(person_pk)`;
`fk_person_address_type FOREIGN KEY (address_type_pk) REFERENCES
address_type_master(address_type_pk)`; `fk_person_address_location FOREIGN KEY
(city_village_postal_code_map_pk) REFERENCES
city_village_postal_code_map(city_village_postal_code_map_pk)` — this is the one place this
prototype actually reaches into a real (non-superseded) Foundation table. No soft-delete CHECK
constraint here either, same gap as `person`.

Indexes: `idx_person_address_person (person_pk)`, `idx_person_address_type (address_type_pk)`,
`idx_person_address_location (city_village_postal_code_map_pk)`, `idx_person_address_active
(is_active)`.

Additionally: `CREATE UNIQUE INDEX uq_person_primary_address ON person_address(person_pk) WHERE
is_primary = TRUE;` — a **partial unique index**, not a table-level `CONSTRAINT`, because
"at most one row per person with `is_primary = TRUE`" cannot be expressed as an ordinary `CHECK`
(CHECK constraints only see one row at a time; enforcing a cross-row invariant requires either a
partial unique index like this one or a trigger). This is the mechanism that guarantees a person
can never have two primary addresses simultaneously.

---

### database/seed/03_person/01_person_master_tables.sql

> **SUPERSEDED PROTOTYPE — not executed by `02_build.sh`/`02_build.ps1`, kept for reference
> only.** Seeds into the non-existent-in-production tables described above
> (`gender_master`/`marital_status_master`/`address_type_master`), not into `nss.master_data`.

**Requirement (as originally written)**

Seeds the three prototype master tables with the same values Foundation's `master_data` seed
provides under `GENDER`, `MARITAL_STATUS`, and `ADDRESS_TYPE` — illustrating directly why the
prototype was superseded: this data is fully duplicated by the generic pattern, just split
across three dedicated tables instead of one shared `master_data` table filtered by category.

**Line-by-line explanation**

```sql
INSERT INTO gender_master
(
    gender_code,
    gender_name,
    display_order
)
VALUES
('MALE', 'Male', 1),
('FEMALE', 'Female', 2),
('OTHER', 'Other', 3);

INSERT INTO marital_status_master
(
    marital_status_code,
    marital_status_name,
    display_order
)
VALUES
('UNMARRIED', 'Unmarried', 1),
('MARRIED', 'Married', 2),
('WIDOWED', 'Widowed', 3),
('DIVORCED', 'Divorced', 4),
('SEPARATED', 'Separated', 5);

INSERT INTO address_type_master
(
    address_type_code,
    address_type_name,
    display_order
)
VALUES
('PERMANENT', 'Permanent Address', 1),
('CURRENT', 'Current Address', 2),
('OFFICIAL', 'Official Address', 3);
```

Three plain `INSERT INTO <table> (<code_col>, <name_col>, display_order) VALUES (...);`
statements, one per table, all schema-unqualified (consistent with the DDL):

- **`gender_master` (3 rows):** `('MALE', 'Male', 1)`, `('FEMALE', 'Female', 2)`, `('OTHER',
  'Other', 3)` — identical values/order to Foundation's `GENDER` master_data rows.
- **`marital_status_master` (5 rows):** `('UNMARRIED', 'Unmarried', 1)`, `('MARRIED',
  'Married', 2)`, `('WIDOWED', 'Widowed', 3)`, `('DIVORCED', 'Divorced', 4)`, `('SEPARATED',
  'Separated', 5)` — identical to Foundation's `MARITAL_STATUS` master_data rows.
- **`address_type_master` (3 rows):** `('PERMANENT', 'Permanent Address', 1)`, `('CURRENT',
  'Current Address', 2)`, `('OFFICIAL', 'Official Address', 3)` — identical to Foundation's
  `ADDRESS_TYPE` master_data rows.

Total row count: **11** across the three tables (3 + 5 + 3), all values-for-values duplicates of
rows already present in `nss.master_data` once `database/seed/01_foundation/02_master_data.sql`
has run.

---

### database/ddl/04_family/01_family_group.sql

> **Real, implemented DDL** — executed by `database/scripts/02_build.sh`/`02_build.ps1`, unlike
> the `03_person/` prototype documented immediately above. Family (Tier 4) is built against the
> same frozen `master_category`/`master_data` pattern Organization and the real Person DDL use,
> not the superseded per-domain-master-table style.

**Requirement**

Defines `nss.family_group` — the root table of the Family module: one row per family unit, tying
it to the Sakha it's registered under and a lifecycle status resolved through Foundation's
unified `STATUS` category. Depth 2 (depends on `organization`, `master_data`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.family_group
(
    family_group_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    family_id VARCHAR(20) NOT NULL,

    family_name VARCHAR(200) NOT NULL,

    family_status_master_data_pk UUID NOT NULL,

    sakha_organization_pk UUID NOT NULL,

    formed_date DATE NULL,

    remarks TEXT NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,
```

Columns: `family_group_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()` — schema-qualified
(`nss.family_group`), consistent with every real (non-superseded) table in this document;
`family_id VARCHAR(20) NOT NULL` — the business identifier (e.g. `F1`), following the
project-wide **unpadded** ID convention adopted across this branch (see
`docs/00_Project_Governance/STD/01_project_standards.md`) rather than the earlier zero-padded
style (`F00000001`); `family_name VARCHAR(200) NOT NULL`; `family_status_master_data_pk UUID NOT
NULL` — FK into `nss.master_data`, unified `STATUS` category, not a dedicated
`family_status_master` table; `sakha_organization_pk UUID NOT NULL` — FK into
`nss.organization`, the Sakha this family is registered under; `formed_date DATE NULL`; `remarks
TEXT NULL`; then the standard soft-delete/audit block: `is_active BOOLEAN NOT NULL DEFAULT TRUE`,
`created_at`/`updated_at`/`deleted_at TIMESTAMPTZ`, and three nullable
`*_by_sangha_sevi_pk UUID` audit-actor columns whose FK constraints are deferred to Pass 2 (after
`sangha_sevi` exists) — same two-pass strategy Organization and Person's real DDL both use.

```sql
    CONSTRAINT uq_family_id
        UNIQUE (family_id),

    CONSTRAINT fk_family_group_status
        FOREIGN KEY (family_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_family_group_sakha
        FOREIGN KEY (sakha_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_family_group_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_family_group_family_id
    ON nss.family_group (family_id);

CREATE INDEX idx_family_group_sakha
    ON nss.family_group (sakha_organization_pk);

CREATE INDEX idx_family_group_status
    ON nss.family_group (family_status_master_data_pk);

CREATE INDEX idx_family_group_is_active
    ON nss.family_group (is_active);

CREATE INDEX idx_family_group_family_name
    ON nss.family_group (family_name);
```

Constraints: `uq_family_id UNIQUE (family_id)` — every family's business ID is globally unique;
`fk_family_group_status` and `fk_family_group_sakha` — both plain (non-`LEFT`) FKs, matching that
both source columns are `NOT NULL`; `chk_family_group_soft_delete` — the same
`is_active`/`deleted_at` consistency CHECK used by `organization` and every other real
(non-prototype) table in this schema.

Indexes: `idx_family_group_family_id`, `idx_family_group_sakha`, `idx_family_group_status`,
`idx_family_group_is_active`, `idx_family_group_family_name` — one per FK/filter column, the same
"index every FK and every commonly-filtered column" convention used throughout `nss.*`.

---

### database/ddl/04_family/02_family_relationship.sql

**Requirement**

Defines `nss.family_relationship` — one row per (family, person, relationship type), the table
that actually places a person *inside* a family unit with a typed, effective-dated relationship.
Depth 3 (depends on `family_group`, `person`, `master_data`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.family_relationship
(
    family_relationship_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    family_group_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    relationship_type_master_data_pk UUID NOT NULL,

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    is_current BOOLEAN NOT NULL
        DEFAULT TRUE,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,
```

Columns: `family_relationship_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`;
`family_group_pk UUID NOT NULL` — FK to `family_group`; `person_pk UUID NOT NULL` — FK to
`nss.person`; `relationship_type_master_data_pk UUID NOT NULL` — FK into `nss.master_data`,
category `RELATIONSHIP_TYPE` (FATHER, MOTHER, SPOUSE, SON, DAUGHTER, etc. — the same category
Person's own `emergency_relationship_master_data_pk` column draws from); `effective_from DATE NOT
NULL`, `effective_to DATE NULL` — the effective-dated period this relationship is/was in force;
`is_current BOOLEAN NOT NULL DEFAULT TRUE`; `remarks TEXT NULL`. Note this table has only a
two-column audit-actor pair (`created_by_sangha_sevi_pk`, `updated_by_sangha_sevi_pk`) and no
`deleted_at`/`deleted_by_sangha_sevi_pk` — relationship rows are effective-dated and superseded
(a new row with a later `effective_from` and the old row's `effective_to`/`is_current` updated),
not soft-deleted the way `family_group` is.

```sql
    CONSTRAINT fk_family_rel_family_group
        FOREIGN KEY (family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_rel_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_family_rel_type
        FOREIGN KEY (relationship_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_family_rel_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        ),

    CONSTRAINT chk_family_rel_current_consistency
        CHECK
        (
            (is_current = TRUE AND effective_to IS NULL)
            OR
            (is_current = FALSE AND effective_to IS NOT NULL)
        )
);

CREATE INDEX idx_family_rel_family_group
    ON nss.family_relationship (family_group_pk);

CREATE INDEX idx_family_rel_person
    ON nss.family_relationship (person_pk);

CREATE INDEX idx_family_rel_type
    ON nss.family_relationship (relationship_type_master_data_pk);

CREATE INDEX idx_family_rel_is_current
    ON nss.family_relationship (is_current);

CREATE UNIQUE INDEX uq_family_rel_person_current
    ON nss.family_relationship (family_group_pk, person_pk)
    WHERE is_current = TRUE;
```

Constraints: three plain FKs (`fk_family_rel_family_group`, `fk_family_rel_person`,
`fk_family_rel_type`); `chk_family_rel_effective_range CHECK (effective_to IS NULL OR
effective_to >= effective_from)` — an ended relationship can't end before it started;
`chk_family_rel_current_consistency CHECK ((is_current = TRUE AND effective_to IS NULL) OR
(is_current = FALSE AND effective_to IS NOT NULL))` — ties the boolean flag to the date column so
they can never drift out of sync.

Indexes: the standard per-FK set (`idx_family_rel_family_group`, `idx_family_rel_person`,
`idx_family_rel_type`) plus `idx_family_rel_is_current`. The final index is the interesting one:

```sql
CREATE UNIQUE INDEX uq_family_rel_person_current
    ON nss.family_relationship (family_group_pk, person_pk)
    WHERE is_current = TRUE;
```

A **partial unique index** — enforces "at most one current relationship per (family, person)
pair" without constraining historical rows at all, since a person may accumulate multiple past
relationship rows in the same family (e.g. a corrected or superseded relationship type) as long
as only one of them is ever flagged `is_current = TRUE`. Same technique as Person's
`uq_person_primary_address`.

---

### database/ddl/04_family/03_family_head_history.sql

**Requirement**

Defines `nss.family_head_history` — an append-only log of who has headed each family and when,
never mutated in place once a head's tenure ends (per the frozen "History Never Deleted"
principle, FAM-028). Depth 3 (depends on `family_group`, `person`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.family_head_history
(
    family_head_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    family_group_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    reason VARCHAR(500) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_family_head_family_group
        FOREIGN KEY (family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_head_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT chk_family_head_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        )
);

CREATE INDEX idx_family_head_family_group
    ON nss.family_head_history (family_group_pk);

CREATE INDEX idx_family_head_person
    ON nss.family_head_history (person_pk);

CREATE UNIQUE INDEX uq_family_head_current
    ON nss.family_head_history (family_group_pk)
    WHERE effective_to IS NULL;
```

Columns: `family_head_history_pk`, `family_group_pk`/`person_pk` (both `NOT NULL` FKs),
`effective_from DATE NOT NULL`/`effective_to DATE NULL`, `reason VARCHAR(500) NULL` (why the
headship changed), `remarks TEXT NULL`. Audit is deliberately minimal here — only `created_at`
and `created_by_sangha_sevi_pk`, no `updated_at`/`updated_by`/`deleted_at`/`deleted_by` at all —
because a history row, once written, is never updated or deleted; the only "change" a headship
record undergoes is a later row setting this one's `effective_to` (via an `UPDATE` on
`effective_to` alone) when a new head takes over, and even that touches exactly one column, not
the row's substantive facts.

Constraints: the two plain FKs, plus `chk_family_head_effective_range` — the same
"can't end before it started" CHECK as `family_relationship`.

Indexes: `idx_family_head_family_group`, `idx_family_head_person`, and the table's defining
invariant:

```sql
CREATE UNIQUE INDEX uq_family_head_current
    ON nss.family_head_history (family_group_pk)
    WHERE effective_to IS NULL;
```

A partial unique index guaranteeing **at most one row per family group with `effective_to IS
NULL`** — i.e. exactly one current head at any given time, while every past head's row (with
`effective_to` set) is left untouched and unconstrained by this index.

---

### database/ddl/04_family/04_family_transition_history.sql

**Requirement**

Defines `nss.family_transition_history` — an append-only log of a person moving from one family
group to another (marriage, new-family formation, change of family unit), preserving both the
origin and destination family groups rather than overwriting `family_relationship` rows in place
(FAM-013, FAM-028). Depth 3 (depends on `family_group` twice, `person`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.family_transition_history
(
    family_transition_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    person_pk UUID NOT NULL,

    old_family_group_pk UUID NOT NULL,

    new_family_group_pk UUID NOT NULL,

    transition_type VARCHAR(50) NOT NULL,

    transition_reason VARCHAR(500) NULL,

    effective_date DATE NOT NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_family_trans_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_family_trans_old_family
        FOREIGN KEY (old_family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_trans_new_family
        FOREIGN KEY (new_family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT chk_family_trans_different_families
        CHECK (old_family_group_pk <> new_family_group_pk),

    CONSTRAINT chk_family_trans_type
        CHECK
        (
            transition_type IN
            (
                'MARRIAGE',
                'NEW_FAMILY_FORMATION',
                'CHANGE_OF_FAMILY_UNIT',
                'OTHER'
            )
        )
);

CREATE INDEX idx_family_trans_person
    ON nss.family_transition_history (person_pk);

CREATE INDEX idx_family_trans_old_family
    ON nss.family_transition_history (old_family_group_pk);

CREATE INDEX idx_family_trans_new_family
    ON nss.family_transition_history (new_family_group_pk);

CREATE INDEX idx_family_trans_effective_date
    ON nss.family_transition_history (effective_date);

CREATE INDEX idx_family_trans_type
    ON nss.family_transition_history (transition_type);
```

Columns: `person_pk UUID NOT NULL` — the person who transitioned; `old_family_group_pk`/
`new_family_group_pk UUID NOT NULL` — **two separate FKs to the same table**
(`nss.family_group`), both required, so both the origin and destination family are always
recorded; `transition_type VARCHAR(50) NOT NULL` — a plain, CHECK-constrained code column, not a
`master_data` FK (see below); `transition_reason VARCHAR(500) NULL`; `effective_date DATE NOT
NULL`; `remarks TEXT NULL`; the same minimal `created_at`/`created_by_sangha_sevi_pk`-only audit
pair as `family_head_history` — another append-only, never-updated history table.

Constraints: `fk_family_trans_person`, `fk_family_trans_old_family`, `fk_family_trans_new_family`
— three plain FKs; `chk_family_trans_different_families CHECK (old_family_group_pk <>
new_family_group_pk)` — a transition must actually move the person between two *distinct*
families, rejecting a no-op "transition" to the same family at the database level;
`chk_family_trans_type CHECK (transition_type IN ('MARRIAGE', 'NEW_FAMILY_FORMATION',
'CHANGE_OF_FAMILY_UNIT', 'OTHER'))` — a closed four-value enumeration enforced directly by CHECK
rather than routed through Foundation's `master_data` pattern, since the value set is small,
fixed, and carries no display-name/sort-order metadata worth modeling as reference data (unlike,
say, `RELATIONSHIP_TYPE` or `STATUS`).

Indexes: one per FK (`idx_family_trans_person`, `idx_family_trans_old_family`,
`idx_family_trans_new_family`) plus `idx_family_trans_effective_date` and
`idx_family_trans_type` — the latter two support querying a person's transition timeline in date
order and filtering/reporting by transition type.

---

### database/ddl/04_family/05_family_link.sql

**Requirement**

Defines `nss.family_link` — the fifth table added to the Family module, and a **different**
kind of table from the other four: instead of resolving a family member's kinship *label*
against a lookup category, it stores only the raw, directed biological/legal edges
(`PARENT_OF`, `SPOUSE_OF`) between two persons in a family, leaving every other kinship term
(Grandfather, Cousin, Sister-in-Law, ...) to be computed at query time by graph traversal
relative to whoever is viewing the family (`api/services/family_graph.py` — see
`docs/03_Solution/code_explanations/API_CODE_EXPLANATIONS.md` §2.15). Depth 3 (depends on
`family_group`, `person`, same depth as `family_relationship`/`family_head_history`). Without
this table, the graph endpoint (`GET /families/{family_group_pk}/graph`) would have nothing to
traverse — `family_relationship` alone records *family-unit membership* (who belongs to the
family and their static relationship-type code), not the *direct edges* a graph algorithm needs
to derive extended kinship dynamically.

**Line-by-line explanation**

Lines 1–21 — header comment (Authority + design rationale):

```sql
-- =====================================================
-- NSS ERP
-- Module: Family
-- File: 05_family_link.sql
-- Table: nss.family_link
-- Depth: 3 (depends on family_group, person)
-- Version: 1.0
-- Authority: ERP-DECISION — Graph-based dynamic
--            relationship model
-- Owner: NSS_ERP_ADMIN
-- Note: Stores only direct biological/legal edges
--       between family members. All extended
--       relationships (grandfather, uncle, cousin,
--       etc.) are computed dynamically via graph
--       traversal relative to the viewer.
--
--       link_type semantics:
--         PARENT_OF — person_a is parent of person_b
--         SPOUSE_OF — person_a and person_b are spouses
--                     (bidirectional; store one row)
-- =====================================================
```

Authority is `ERP-DECISION — Graph-based dynamic relationship model` — a distinct authority tag
from `SOL-FAM-005`/`SOL-FAM-003`/`SOL-ARCH-010`, which govern the other four Family tables (per
`database/ddl/04_family/README.md`) — signalling this table implements a specific, separately
decided design choice rather than the original Family module design doc. The comment states the
rationale this whole file exists to encode: only *direct* edges are persisted; every derived
kinship label is computed, never stored, which is why the module needs no `KINSHIP_TYPE` master
data category no matter how many labels `PATH_LABELS` (in `family_graph.py`) eventually grows to
cover. It also documents `link_type`'s two-value semantics inline: `PARENT_OF` is a *directed*
edge (`person_a_pk` is the parent, `person_b_pk` the child), while `SPOUSE_OF` is conceptually
*bidirectional* but the convention is to store exactly one row per couple, not two — the
traversal code (`FamilyGraph.add_link`) is what expands that single stored row into two adjacency
entries at read time, not the DDL.

```sql
CREATE TABLE nss.family_link
(
    family_link_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    family_group_pk UUID NOT NULL,

    -- The "from" person in the directed edge
    person_a_pk UUID NOT NULL,

    -- The "to" person in the directed edge
    person_b_pk UUID NOT NULL,

    -- Only two link types allowed
    link_type VARCHAR(20) NOT NULL,

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    is_current BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_family_link_family_group
        FOREIGN KEY (family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_link_person_a
        FOREIGN KEY (person_a_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_family_link_person_b
        FOREIGN KEY (person_b_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT chk_family_link_type
        CHECK (link_type IN ('PARENT_OF', 'SPOUSE_OF')),

    CONSTRAINT chk_family_link_no_self
        CHECK (person_a_pk <> person_b_pk),

    CONSTRAINT chk_family_link_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        ),

    CONSTRAINT chk_family_link_current_consistency
        CHECK
        (
            (is_current = TRUE AND effective_to IS NULL)
            OR
            (is_current = FALSE AND effective_to IS NOT NULL)
        )
);
```

Columns: `family_link_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()` — the standard PK shape
shared by every table in this document; `family_group_pk UUID NOT NULL` — which family this edge
belongs to (an edge is always scoped to one family, never cross-family); `person_a_pk`/
`person_b_pk UUID NOT NULL` — the two endpoints of the directed edge, named generically ("from"/
"to" per the inline comments) rather than e.g. `parent_pk`/`child_pk`, because the same pair of
columns serves both `PARENT_OF` (directional) and `SPOUSE_OF` (nominally symmetric but stored
once) edge types; `link_type VARCHAR(20) NOT NULL` — the two-value edge type discussed above;
`effective_from DATE NOT NULL` / `effective_to DATE NULL` / `is_current BOOLEAN NOT NULL DEFAULT
TRUE` — the same effective-dated triple `family_relationship` uses, so an edge (e.g. a marriage
that later ends, or a corrected parentage record) can be superseded without being deleted, per
the "History Never Deleted" principle; audit columns are `created_at`/`created_by_sangha_sevi_pk`/
`updated_at`/`updated_by_sangha_sevi_pk` only — no `deleted_at`/`deleted_by_sangha_sevi_pk` and no
`is_active`, unlike `family_group`/`family_relationship` — because a link's lifecycle is already
fully expressed by `is_current`/`effective_to` (a link is either current, or historical-but-kept,
never "soft-deleted" as a separate state); like every other Family/Person/Organization table, the
`*_by_sangha_sevi_pk` audit-actor FKs are nullable, unconstrained columns in this pass (Pass 2 FK
constraints deferred until `sangha_sevi` exists, per `database/ddl/04_family/README.md`).

Constraints: `fk_family_link_family_group`, `fk_family_link_person_a`, `fk_family_link_person_b`
— three plain FKs (`family_group`, and `person` referenced *twice* under two different FK names,
the same "two FKs to the same table" idiom `family_transition_history` uses for its
`old_family_group_pk`/`new_family_group_pk`); `chk_family_link_type CHECK (link_type IN
('PARENT_OF', 'SPOUSE_OF'))` — the closed two-value enumeration, enforced the same
CHECK-not-master_data way `family_transition_history.transition_type` is, for the same reason (a
small, fixed, metadata-free code set); `chk_family_link_no_self CHECK (person_a_pk <>
person_b_pk)` — a person cannot be their own parent or spouse, the same
"self-referencing-pair must differ" idiom used elsewhere in the schema (e.g.
`chk_family_trans_different_families`); `chk_family_link_effective_range` — the standard
"can't end before it started" CHECK, identical in shape to `family_relationship`'s own effective-
range constraint; `chk_family_link_current_consistency` — ties `is_current` to `effective_to`,
the same pattern as `chk_family_rel_current_consistency` on `family_relationship`: a current edge
must have `effective_to IS NULL`, a historical one must have it set, so which is true is always
derivable from either column without them drifting out of sync.

```sql
CREATE INDEX idx_family_link_family_group
    ON nss.family_link (family_group_pk);

CREATE INDEX idx_family_link_person_a
    ON nss.family_link (person_a_pk);

CREATE INDEX idx_family_link_person_b
    ON nss.family_link (person_b_pk);

CREATE INDEX idx_family_link_is_current
    ON nss.family_link (is_current);

-- A given directed edge should not be duplicated
-- while current.
CREATE UNIQUE INDEX uq_family_link_current
    ON nss.family_link (family_group_pk, person_a_pk, person_b_pk, link_type)
    WHERE is_current = TRUE;
```

Indexes: one per FK (`idx_family_link_family_group`, `idx_family_link_person_a`,
`idx_family_link_person_b`) — the standard per-FK set, and specifically what makes
`api/routers/family.py`'s `_GRAPH_PERSONS_SQL`/`_GRAPH_LINKS_SQL` (filtered by
`family_group_pk`) efficient; plus `idx_family_link_is_current`, supporting the
`WHERE is_current = TRUE` filter both of those queries also apply. `uq_family_link_current` is a
**partial unique index** (not a table-level `UNIQUE` constraint) on `(family_group_pk,
person_a_pk, person_b_pk, link_type) WHERE is_current = TRUE` — the same partial-unique-index
technique `uq_family_rel_person_current`/`uq_family_head_current` already use elsewhere in this
module: it prevents the *same directed edge* (e.g. "A is parent of B") from being recorded twice
while current, without blocking a historical (`is_current = FALSE`) duplicate of a
superseded/corrected edge from coexisting alongside its replacement.

---

### database/seed/04_family/01_tier4_verification_family.sql

**Requirement**

Seeds one realistic family (`F1`, "Mishra Paribara") with three current members and one head
assignment, so the Family UI (originally the `/family` Verification UI, now `dashboard.html`'s
Family tab) and `tests/test_family.py` have concrete
data to render and assert against — the same verification-data role Organization's/Bootstrap's
seed files play for their own tiers, and a sharp contrast with Person's own seed file (zero
rows) referenced above.

**Line-by-line explanation**

```sql
INSERT INTO nss.family_group
    (family_id, family_name, family_status_master_data_pk,
     sakha_organization_pk, formed_date)
SELECT
    'F1',
    'Mishra Paribara',
    st.master_data_pk,
    sakha.organization_pk,
    '2010-04-01'
FROM nss.master_data st
JOIN nss.master_category mc ON mc.master_category_pk = st.master_category_pk
CROSS JOIN nss.organization sakha
WHERE mc.category_code = 'STATUS' AND st.value_code = 'ACTIVE'
  AND sakha.organization_code = 'SKH1';
```

An `INSERT ... SELECT` rather than a literal `INSERT ... VALUES` with a hardcoded UUID, because
`family_status_master_data_pk` and `sakha_organization_pk` are both `gen_random_uuid()`-generated
values assigned when Foundation's/Organization's own seed data was inserted, not known in
advance. The `SELECT` resolves `st.master_data_pk` by filtering `nss.master_data` joined to
`nss.master_category` on `category_code = 'STATUS'` and `value_code = 'ACTIVE'`, and
`sakha.organization_pk` by filtering `nss.organization` on `organization_code = 'SKH1'` (Ekamra
Sakha) via a `CROSS JOIN` — safe here because the two filtered sources are each expected to
resolve to exactly one row, making the cross product a single row overall. Inserts `family_id =
'F1'` (unpadded, per the project's ID convention), `family_name = 'Mishra Paribara'`, and
`formed_date = '2010-04-01'`.

```sql
INSERT INTO nss.family_relationship
    (family_group_pk, person_pk, relationship_type_master_data_pk,
     effective_from, is_current)
SELECT
    fg.family_group_pk,
    p.person_pk,
    rt.master_data_pk,
    '2010-04-01',
    TRUE
FROM nss.family_group fg
CROSS JOIN nss.person p
CROSS JOIN nss.master_data rt
JOIN nss.master_category mc ON mc.master_category_pk = rt.master_category_pk
WHERE fg.family_id = 'F1'
  AND p.person_id = 'P1'
  AND mc.category_code = 'RELATIONSHIP_TYPE'
  AND rt.value_code = 'FATHER';
```

Three near-identical `INSERT ... SELECT` statements (only shown once above; the other two swap
`p.person_id = 'P1'`/`rt.value_code = 'FATHER'` for `'P2'`/`'SPOUSE'` and `'P3'`/`'SON'`) each
resolve `family_group_pk` by `family_id = 'F1'`, `person_pk` by `person_id` (`P1`/`P2`/`P3` —
unpadded person IDs, matching Person's own convention), and `relationship_type_master_data_pk` by
`category_code = 'RELATIONSHIP_TYPE'` and the appropriate `value_code`. All three set
`effective_from = '2010-04-01'` (matching the family's own `formed_date`) and
`is_current = TRUE` — Ramesh Mishra (`P1`) as FATHER, Sushma Mishra (`P2`) as SPOUSE, Aniket
Mishra (`P3`) as SON.

```sql
INSERT INTO nss.family_head_history
    (family_group_pk, person_pk, effective_from)
SELECT
    fg.family_group_pk,
    p.person_pk,
    '2010-04-01'
FROM nss.family_group fg
CROSS JOIN nss.person p
WHERE fg.family_id = 'F1'
  AND p.person_id = 'P1';
```

The final `INSERT` seeds `family_head_history` with Ramesh Mishra (`P1`) as head since
`2010-04-01`, leaving `effective_to` unset (`NULL` by omission) — per
`uq_family_head_current`'s partial-unique-index invariant, this makes him the family's **current**
head.

Total row count: **1** `family_group` row, **3** `family_relationship` rows, **1**
`family_head_history` row, **0** `family_transition_history` rows (a fresh family has no
transition events yet — that table is populated only once a member later moves between family
groups). See `database/seed/04_family/README.md` for the full row-count table and the ordering
dependency this seed file has on Foundation, Organization, and Person seed data already being
present.

---

### database/ddl/05_membership/01_sangha_sevi.sql

> **Real, implemented DDL** — executed by `database/scripts/02_build.sh`/`02_build.ps1`. Depth 2
> (depends on `person`, `master_data` ×2, `organization`).

**Requirement**

Defines `nss.sangha_sevi` — the Membership module's root table and the record every other table
in this folder hangs off. One row per membership; `UNIQUE (person_pk)` is the DB-level
enforcement of the frozen "One Person = One Membership" principle. Carries the permanent,
NSS-wide **Sangha Sevi ID** (Tier 1 of the three-tier identity model — see
`database/ddl/05_membership/README.md`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.sangha_sevi
(
    sangha_sevi_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_id VARCHAR(20) NOT NULL,

    person_pk UUID NOT NULL,

    membership_type_master_data_pk UUID NOT NULL,

    membership_status_master_data_pk UUID NOT NULL,

    organization_pk UUID NOT NULL,

    joining_date DATE NOT NULL,

    renewal_due_date DATE NULL,

    remarks TEXT NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,
```

Columns: `sangha_sevi_pk UUID PRIMARY KEY DEFAULT gen_random_uuid()`; `sangha_sevi_id VARCHAR(20)
NOT NULL` — the business identifier, format `SS1`, `SS2`, … up to an 8-digit sequence, **no
zero-padding** (the project-wide loosened-padding decision, same as `family_id`/`person_id`);
`person_pk UUID NOT NULL` — FK to `nss.person`; `membership_type_master_data_pk UUID NOT NULL` —
FK into `nss.master_data`, category `MEMBERSHIP_TYPE` (PROBATIONARY/REGULAR/ASSOCIATE/HONORARY);
`membership_status_master_data_pk UUID NOT NULL` — FK into `nss.master_data`, the unified
`STATUS` category (not a dedicated `membership_status_master`); `organization_pk UUID NOT NULL` —
FK to `nss.organization`, the member's *current* Sakha (the authoritative affiliation history
lives on `membership_sakha_affiliation`, not here); `joining_date DATE NOT NULL`;
`renewal_due_date DATE NULL`; `remarks TEXT NULL`; then the standard soft-delete/audit block
(`is_active`, `created_at`/`updated_at`/`deleted_at`, three nullable `*_by_sangha_sevi_pk`
audit-actor columns deferred to Pass 2).

```sql
    CONSTRAINT uq_sangha_sevi_id
        UNIQUE (sangha_sevi_id),

    CONSTRAINT uq_sangha_sevi_person
        UNIQUE (person_pk),

    CONSTRAINT fk_sangha_sevi_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_sangha_sevi_membership_type
        FOREIGN KEY (membership_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_sangha_sevi_status
        FOREIGN KEY (membership_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_sangha_sevi_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_sangha_sevi_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    CONSTRAINT chk_sangha_sevi_renewal_after_joining
        CHECK
        (
            renewal_due_date IS NULL
            OR renewal_due_date >= joining_date
        )
);

CREATE INDEX idx_sangha_sevi_id ON nss.sangha_sevi (sangha_sevi_id);
CREATE INDEX idx_sangha_sevi_person ON nss.sangha_sevi (person_pk);
CREATE INDEX idx_sangha_sevi_type ON nss.sangha_sevi (membership_type_master_data_pk);
CREATE INDEX idx_sangha_sevi_status ON nss.sangha_sevi (membership_status_master_data_pk);
CREATE INDEX idx_sangha_sevi_organization ON nss.sangha_sevi (organization_pk);
CREATE INDEX idx_sangha_sevi_is_active ON nss.sangha_sevi (is_active);
CREATE INDEX idx_sangha_sevi_joining_date ON nss.sangha_sevi (joining_date);

CREATE INDEX idx_sangha_sevi_renewal_due
    ON nss.sangha_sevi (renewal_due_date)
    WHERE renewal_due_date IS NOT NULL;
```

Constraints: `uq_sangha_sevi_id UNIQUE (sangha_sevi_id)` — the Sangha Sevi ID is globally unique
(and, per the header comment, never reused even after a member leaves); `uq_sangha_sevi_person
UNIQUE (person_pk)` — the actual DB-level enforcement of "One Person = One Membership"; three
plain FKs (`fk_sangha_sevi_person`, `_membership_type`, `_status`, `_organization` — all `NOT
NULL` source columns); `chk_sangha_sevi_soft_delete` — the standard `is_active`/`deleted_at`
consistency CHECK; `chk_sangha_sevi_renewal_after_joining CHECK (renewal_due_date IS NULL OR
renewal_due_date >= joining_date)` — a temporal sanity constraint with no equivalent on
`organization`/`family_group` (neither has a comparable date pair).

Indexes: one per FK/filter column (`sangha_sevi_id`, `person_pk`, type, status, organization,
`is_active`, `joining_date`), plus `idx_sangha_sevi_renewal_due` — a **partial index**
(`WHERE renewal_due_date IS NOT NULL`) rather than a full index, since a renewal-due-date lookup
(e.g. "which members need to renew soon") only ever cares about the non-null subset — the same
partial-index-for-a-nullable-filter-column idiom used elsewhere in this schema (e.g.
`idx_pp_affiliated_org` further below).

---

### database/ddl/05_membership/02_membership_status_history.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`, `master_data`).

**Requirement**

Defines `nss.membership_status_history` — the append-only timeline of every status change a
member goes through (ACTIVE/SUSPENDED/LAPSED/…). The *current* status still lives on
`sangha_sevi.membership_status_master_data_pk`; this table exists purely so status history is
never lost, the first instance of the "current state + history" pairing pattern this module uses
repeatedly (see `database/ddl/05_membership/README.md`).

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_status_history
(
    membership_status_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    membership_status_master_data_pk UUID NOT NULL,

    effective_from TIMESTAMPTZ NOT NULL,

    effective_to TIMESTAMPTZ NULL,

    reason VARCHAR(500) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_mem_status_hist_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_status_hist_status
        FOREIGN KEY (membership_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_mem_status_hist_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        )
);

CREATE INDEX idx_mem_status_hist_sevi ON nss.membership_status_history (sangha_sevi_pk);
CREATE INDEX idx_mem_status_hist_status ON nss.membership_status_history (membership_status_master_data_pk);
CREATE INDEX idx_mem_status_hist_effective ON nss.membership_status_history (effective_from);
```

Columns: `membership_status_history_pk UUID PRIMARY KEY`; `sangha_sevi_pk UUID NOT NULL` — FK,
the member this status period belongs to; `membership_status_master_data_pk UUID NOT NULL` — FK,
the status value active during this period; `effective_from`/`effective_to TIMESTAMPTZ` — note
**`TIMESTAMPTZ`**, not `DATE`, unlike almost every other effective-dated column in this module
(`membership_sakha_affiliation.effective_from` is `DATE`) — a status change is timestamped to
the moment it happened, not just the calendar day; `reason VARCHAR(500) NULL`; `remarks TEXT
NULL`; a lighter two-column audit block (`created_at`/`created_by_sangha_sevi_pk` only — no
`updated_at`/`deleted_at`, since a history row, once written, is never edited or soft-deleted).

Constraints: two plain FKs; `chk_mem_status_hist_range CHECK (effective_to IS NULL OR
effective_to >= effective_from)` — the same open-ended-until-closed temporal-range pattern used
by `membership_sakha_affiliation.effective_from`/`effective_to` and
`family_relationship`/`family_head_history`.

Indexes: one per FK column plus `idx_mem_status_hist_effective (effective_from)` for
chronological queries.

---

### database/ddl/05_membership/03_membership_renewal_request.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`).

**Requirement**

Defines `nss.membership_renewal_request` — a request/approval **workflow** row created before a
renewal is granted (`PENDING` → `APPROVED`/`REJECTED`). Distinct from
`membership_renewal_history` (below): a request can be rejected and is itself mutable until
reviewed; a history row is a permanent record that a renewal actually happened.

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_renewal_request
(
    membership_renewal_request_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    requested_date DATE NOT NULL,

    requested_by_sangha_sevi_pk UUID NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'PENDING',

    reviewed_by_sangha_sevi_pk UUID NULL,

    reviewed_date DATE NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_mem_renewal_req_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_mem_renewal_req_status
        CHECK
        (
            status IN ('PENDING', 'APPROVED', 'REJECTED')
        ),

    CONSTRAINT chk_mem_renewal_req_review_consistency
        CHECK
        (
            (status = 'PENDING' AND reviewed_by_sangha_sevi_pk IS NULL AND reviewed_date IS NULL)
            OR
            (status IN ('APPROVED', 'REJECTED') AND reviewed_date IS NOT NULL)
        )
);

CREATE INDEX idx_mem_renewal_req_sevi ON nss.membership_renewal_request (sangha_sevi_pk);
CREATE INDEX idx_mem_renewal_req_status ON nss.membership_renewal_request (status);
CREATE INDEX idx_mem_renewal_req_date ON nss.membership_renewal_request (requested_date);
```

Columns: `membership_renewal_request_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; `requested_date
DATE NOT NULL`; `requested_by_sangha_sevi_pk UUID NULL` — no FK constraint (Pass 2, same as every
other audit-actor column); `status VARCHAR(20) NOT NULL DEFAULT 'PENDING'` — a plain `VARCHAR`
with a CHECK, not an FK to `master_data` (this is a small, fixed, module-internal workflow
enum, not shared reference data); `reviewed_by_sangha_sevi_pk UUID NULL`; `reviewed_date DATE
NULL`; `remarks TEXT NULL`; a two-column audit block (`created_at`/`updated_at` — this table *is*
mutable, unlike the history tables, since a `PENDING` request transitions in place to
`APPROVED`/`REJECTED`).

Constraints: `chk_mem_renewal_req_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))`;
`chk_mem_renewal_req_review_consistency` — a cross-column CHECK enforcing that `PENDING` requests
have **no** reviewer/date yet, while `APPROVED`/`REJECTED` requests **must** have a
`reviewed_date` — the DB-level guarantee that the workflow can't be left in an inconsistent
half-reviewed state.

Indexes: `sangha_sevi_pk`, `status` (for "list all pending requests" queries), `requested_date`.

---

### database/ddl/05_membership/04_membership_renewal_history.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`).

**Requirement**

Defines `nss.membership_renewal_history` — one row per **completed** renewal, permanently
traceable, following the NSS financial year (1 April – 31 March). This is the ledger that a
renewal request table alone can't provide: even if `membership_renewal_request` rows were later
purged or reused, this table's rows are never deleted.

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_renewal_history
(
    membership_renewal_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    renewal_date DATE NOT NULL,

    valid_from DATE NOT NULL,

    valid_to DATE NOT NULL,

    approved_by_sangha_sevi_pk UUID NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mem_renewal_hist_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_mem_renewal_hist_validity
        CHECK (valid_to > valid_from)
);

CREATE INDEX idx_mem_renewal_hist_sevi ON nss.membership_renewal_history (sangha_sevi_pk);
CREATE INDEX idx_mem_renewal_hist_valid_range ON nss.membership_renewal_history (valid_from, valid_to);
```

Columns: `membership_renewal_history_pk`; `sangha_sevi_pk UUID NOT NULL` — FK;
`renewal_date`/`valid_from`/`valid_to DATE NOT NULL` — all three required, unlike the request
table's nullable reviewed fields, since a history row by definition only exists once a renewal is
actually complete; `approved_by_sangha_sevi_pk UUID NULL`; `remarks TEXT NULL`; a single-column
audit block (`created_at` only — no `updated_at`, this table is append-only).

Constraints: one FK; `chk_mem_renewal_hist_validity CHECK (valid_to > valid_from)` — note the
strict `>` (not `>=`), unlike `chk_mem_status_hist_range`'s `>=` — a renewal period can never be
zero-length.

Indexes: `sangha_sevi_pk`; a composite `idx_mem_renewal_hist_valid_range (valid_from, valid_to)`
for "which renewals cover this date" range queries.

---

### database/ddl/05_membership/05_membership_transfer_history.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`, `organization` ×2).

**Requirement**

Defines `nss.membership_transfer_history` — one permanent row per Sakha-to-Sakha transfer. The
member's Sangha Sevi ID is unchanged by a transfer (Tier 1 identity is stable); the
`old_local_sakha_erp_id`/`new_local_sakha_erp_id` columns here are historical **snapshots** for
audit purposes only — the live, authoritative Local Sakha ERP ID history lives on
`membership_sakha_affiliation`.

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_transfer_history
(
    membership_transfer_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    old_organization_pk UUID NOT NULL,

    new_organization_pk UUID NOT NULL,

    transfer_type VARCHAR(50) NOT NULL,

    transfer_reason VARCHAR(500) NULL,

    requested_date DATE NULL,

    approved_date DATE NULL,

    effective_date DATE NOT NULL,

    old_local_sakha_erp_id VARCHAR(30) NULL,

    new_local_sakha_erp_id VARCHAR(30) NULL,

    approved_by_sangha_sevi_pk UUID NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mem_transfer_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_transfer_old_org
        FOREIGN KEY (old_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_mem_transfer_new_org
        FOREIGN KEY (new_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_mem_transfer_different_orgs
        CHECK (old_organization_pk <> new_organization_pk)
);

CREATE INDEX idx_mem_transfer_sevi ON nss.membership_transfer_history (sangha_sevi_pk);
CREATE INDEX idx_mem_transfer_old_org ON nss.membership_transfer_history (old_organization_pk);
CREATE INDEX idx_mem_transfer_new_org ON nss.membership_transfer_history (new_organization_pk);
CREATE INDEX idx_mem_transfer_effective ON nss.membership_transfer_history (effective_date);
```

Columns: `membership_transfer_history_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; **two** FKs into
`nss.organization` from the same table (`old_organization_pk`/`new_organization_pk`) — the same
"two FKs to the same target table, disambiguated by role" shape used elsewhere for
"before/after" relationships; `transfer_type VARCHAR(50) NOT NULL` — free-text-constrained
category (`INTRA_ANCHALIKA`, `INTER_ANCHALIKA`, `INTER_ZILLA`, etc., per the column comment — no
CHECK constraint enumerating them, unlike `affiliation_status`/`source_event_type` on the next
table); `transfer_reason VARCHAR(500) NULL`; `requested_date`/`approved_date DATE NULL`;
`effective_date DATE NOT NULL` — the one required date, since a transfer history row only exists
once it has actually taken effect; `old_local_sakha_erp_id`/`new_local_sakha_erp_id VARCHAR(30)
NULL` — snapshots, explicitly called out in the file's own header comment as "historical
transition snapshots — the authoritative current ID resides on `membership_sakha_affiliation`";
`approved_by_sangha_sevi_pk UUID NULL`; `remarks TEXT NULL`; single-column audit block
(`created_at` only).

Constraints: three FKs; `chk_mem_transfer_different_orgs CHECK (old_organization_pk <>
new_organization_pk)` — a transfer must actually go somewhere different, the same
"self-referencing-pair must differ" idiom `chk_family_relationship_no_self_reference`-style
constraints use elsewhere in this schema.

Indexes: one per FK column (`sangha_sevi_pk`, both organization FKs), plus `effective_date` for
chronological transfer queries.

---

### database/ddl/05_membership/06_membership_sakha_affiliation.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`, `organization`). Frozen per
> `MEM-PENDING-001`.

**Requirement**

Defines `nss.membership_sakha_affiliation` — the **authoritative source of the Local Sakha ERP
ID** (Tier 2 of the three-tier identity model), and the table this module's central frozen
design decision hangs on: the Local Sakha ERP ID lives here, not on `sangha_sevi`, precisely
because it changes on transfer while the Sangha Sevi ID does not.

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_sakha_affiliation
(
    membership_sakha_affiliation_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    organization_pk UUID NOT NULL,

    local_sakha_erp_id VARCHAR(30) NOT NULL,

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    affiliation_status VARCHAR(20) NOT NULL,

    source_event_type VARCHAR(20) NOT NULL,

    source_event_pk UUID NULL,

    legacy_sakha_number VARCHAR(30) NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_mem_sakha_aff_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_sakha_aff_org
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT uq_mem_sakha_aff_local_id
        UNIQUE (organization_pk, local_sakha_erp_id),

    CONSTRAINT chk_mem_sakha_aff_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        ),

    CONSTRAINT chk_mem_sakha_aff_status_consistency
        CHECK
        (
            (effective_to IS NULL AND affiliation_status IN ('ACTIVE', 'REACTIVATED'))
            OR
            (effective_to IS NOT NULL AND affiliation_status = 'ARCHIVED')
        ),

    CONSTRAINT chk_mem_sakha_aff_status
        CHECK
        (
            affiliation_status IN ('ACTIVE', 'ARCHIVED', 'REACTIVATED')
        ),

    CONSTRAINT chk_mem_sakha_aff_event_type
        CHECK
        (
            source_event_type IN ('ENROLLMENT', 'TRANSFER', 'REACTIVATION')
        )
);

CREATE INDEX idx_mem_sakha_aff_sevi ON nss.membership_sakha_affiliation (sangha_sevi_pk);
CREATE INDEX idx_mem_sakha_aff_org ON nss.membership_sakha_affiliation (organization_pk);
CREATE INDEX idx_mem_sakha_aff_status ON nss.membership_sakha_affiliation (affiliation_status);

CREATE UNIQUE INDEX uq_mem_sakha_aff_active
    ON nss.membership_sakha_affiliation (sangha_sevi_pk)
    WHERE effective_to IS NULL;
```

Columns: `membership_sakha_affiliation_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; `organization_pk
UUID NOT NULL` — FK, the Sakha this affiliation row is for; `local_sakha_erp_id VARCHAR(30) NOT
NULL` — **the** Tier 2 identity column, format `<3-5 char Sakha short code><numeric sequence>`
(e.g. `ESS1192`), persistent per person per Sakha, never reassigned; `effective_from DATE NOT
NULL` / `effective_to DATE NULL` — `NULL` means this is the *current* active row;
`affiliation_status VARCHAR(20) NOT NULL` — `ACTIVE`/`ARCHIVED`/`REACTIVATED`; `source_event_type
VARCHAR(20) NOT NULL` — `ENROLLMENT`/`TRANSFER`/`REACTIVATION`, what caused this row to be
created; `source_event_pk UUID NULL` — an optional, untyped (no FK constraint) reference to the
originating event row (e.g. a `membership_transfer_history_pk`) — untyped because the source
could be any one of several different tables depending on `source_event_type`, and Postgres has
no native polymorphic-FK mechanism; `legacy_sakha_number VARCHAR(30) NULL` — the pre-ERP register
number, populated only on migrated records; four-column audit block (`created_at`/`updated_at`
plus their `*_by_sangha_sevi_pk` actors — this table *is* mutable, since closing an affiliation
means updating `effective_to` on the existing row rather than inserting a new one).

Constraints: two plain FKs; `uq_mem_sakha_aff_local_id UNIQUE (organization_pk,
local_sakha_erp_id)` — the Local Sakha ERP ID is unique **per Sakha**, not globally (the same
numeric suffix can recur at a different Sakha — the seed data's `ESS1100`→`CTC1` transfer for
Suresh Patel demonstrates this); `chk_mem_sakha_aff_effective_range` — the standard open-range
CHECK; `chk_mem_sakha_aff_status_consistency` — the constraint tying `effective_to` nullability
to `affiliation_status` (open rows must be `ACTIVE`/`REACTIVATED`; closed rows must be
`ARCHIVED`) — enforced at the DB level, not just application logic; `chk_mem_sakha_aff_status`
and `chk_mem_sakha_aff_event_type` — plain enumeration CHECKs.

Indexes: one per FK column plus `affiliation_status`; and — the single most important index in
this table — `uq_mem_sakha_aff_active`, a **partial unique index** (`WHERE effective_to IS
NULL`) that is the actual DB-level enforcement of "one active affiliation per member at any
time." Like `uq_pp_active_per_member`/`uq_ap_active_per_member` further below, this invariant
can't be expressed as an ordinary table-level CHECK (which only sees one row at a time) — a
partial unique index is the standard PostgreSQL idiom for a "one row per group matching some
condition" rule.

---

### database/ddl/05_membership/07_membership_journey_event.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`).

**Requirement**

Defines `nss.membership_journey_event` — a free-form, chronological timeline of a member's
lifecycle events (enrolment, promotion, transfer, status changes, Kumari transition, etc.),
rendered as a DaisyUI vertical-steps component (originally by `membership.html`, now by
`dashboard.html`'s Membership tab).

**Line-by-line explanation**

```sql
CREATE TABLE nss.membership_journey_event
(
    membership_journey_event_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    event_type VARCHAR(50) NOT NULL,

    event_date DATE NOT NULL,

    event_reference VARCHAR(255) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_mem_journey_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk)
);

CREATE INDEX idx_mem_journey_sevi ON nss.membership_journey_event (sangha_sevi_pk);
CREATE INDEX idx_mem_journey_event_type ON nss.membership_journey_event (event_type);
CREATE INDEX idx_mem_journey_event_date ON nss.membership_journey_event (event_date);
```

Columns: `membership_journey_event_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; `event_type
VARCHAR(50) NOT NULL` — **deliberately not an FK to `master_data`**, per the file's own header
comment ("event catalogue controlled via application layer... event types are extensible and
module-specific") — the one column in this entire module where a `master_data`-style frozen
enumeration was consciously rejected in favour of an open, application-controlled vocabulary
(`MEMBERSHIP_CREATED`, `PROBATIONARY_STARTED`, `TRAINING_STARTED`, `PROBATIONARY_REVIEW`,
`REGULAR_ENROLMENT`, `ASSOCIATE_ENROLMENT`, `RENEWAL`, `TRANSFER`, `STATUS_CHANGE`,
`KUMARI_TRANSITION`, etc., per the seed data); `event_date DATE NOT NULL`; `event_reference
VARCHAR(255) NULL` — optional pointer to a related record (e.g. a transfer or renewal PK,
untyped for the same polymorphic reason as `source_event_pk` above); `remarks TEXT NULL`;
single-actor audit block (`created_at`/`created_by_sangha_sevi_pk` only — append-only, no
`updated_at`).

Constraints: exactly one FK — the simplest constraint set of any table in this module, a direct
reflection of `event_type` carrying no CHECK enumeration.

Indexes: `sangha_sevi_pk`, `event_type` (for cross-member queries like "everyone who transferred
this year"), `event_date` (chronological).

---

### database/ddl/05_membership/08_probationary_member_review.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`).

**Requirement**

Defines `nss.probationary_member_review` — periodic/final/special review checkpoints
(Bye-Law §B(b): at least one year Probationary + one year training before Regular enrolment),
preserving a Probationary member's progression history without overwriting or replacing the
membership record itself.

**Line-by-line explanation**

```sql
CREATE TABLE nss.probationary_member_review
(
    probationary_member_review_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    review_date DATE NOT NULL,

    reviewed_by_sangha_sevi_pk UUID NULL,

    review_type VARCHAR(20) NOT NULL,

    outcome VARCHAR(20) NOT NULL,

    training_completed BOOLEAN NOT NULL
        DEFAULT FALSE,

    sakha_recommendation BOOLEAN NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_prob_review_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_prob_review_type
        CHECK
        (
            review_type IN ('PERIODIC', 'FINAL', 'SPECIAL')
        ),

    CONSTRAINT chk_prob_review_outcome
        CHECK
        (
            outcome IN ('PASS', 'FAIL', 'DEFERRED')
        )
);

CREATE INDEX idx_prob_review_sevi ON nss.probationary_member_review (sangha_sevi_pk);
CREATE INDEX idx_prob_review_date ON nss.probationary_member_review (review_date);
CREATE INDEX idx_prob_review_outcome ON nss.probationary_member_review (outcome);
```

Columns: `probationary_member_review_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; `review_date DATE
NOT NULL`; `reviewed_by_sangha_sevi_pk UUID NULL`; `review_type VARCHAR(20) NOT NULL` —
`PERIODIC`/`FINAL`/`SPECIAL`; `outcome VARCHAR(20) NOT NULL` — `PASS`/`FAIL`/`DEFERRED`;
`training_completed BOOLEAN NOT NULL DEFAULT FALSE`; `sakha_recommendation BOOLEAN NULL` — the
Sakha's recommendation for Regular enrolment, nullable because a periodic review may not yet be
at the recommendation stage; `remarks TEXT NULL`; two-column audit block (`created_at`/
`updated_at` — this table is mutable, unlike the pure-history tables, since a review record could
plausibly be corrected).

Constraints: one FK; two enumeration CHECKs (`review_type`, `outcome`) — this is the only table
in the module with **two** independent small-enum CHECK constraints on separate columns rather
than one.

Indexes: `sangha_sevi_pk`, `review_date`, `outcome` (for "everyone who failed/deferred" queries).

---

### database/ddl/05_membership/09_parichaya_patra.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`, `organization`).

**Requirement**

Defines `nss.parichaya_patra` — the annual Identity Card issued by Kendra Sangha
(Bye-Law §B(b)(iii), §B(d)(i)). `document_number` is the **Kendra Number** (Tier 3 of the
three-tier identity model).

**Line-by-line explanation**

```sql
CREATE TABLE nss.parichaya_patra
(
    parichaya_patra_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    document_number VARCHAR(30) NOT NULL,

    issue_date DATE NOT NULL,

    valid_from DATE NOT NULL,

    valid_to DATE NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    affiliated_organization_pk UUID NULL,

    local_sakha_erp_id VARCHAR(30) NULL,

    document_reference VARCHAR(255) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_pp_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_pp_affiliated_org
        FOREIGN KEY (affiliated_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_pp_validity_range
        CHECK (valid_to > valid_from),

    CONSTRAINT chk_pp_status
        CHECK
        (
            status IN ('ACTIVE', 'EXPIRED', 'CANCELLED', 'REPLACED')
        ),

    CONSTRAINT uq_pp_document_number
        UNIQUE (document_number)
);

CREATE INDEX idx_pp_sevi ON nss.parichaya_patra (sangha_sevi_pk);
CREATE INDEX idx_pp_status ON nss.parichaya_patra (status);
CREATE INDEX idx_pp_valid_range ON nss.parichaya_patra (valid_from, valid_to);

CREATE INDEX idx_pp_affiliated_org
    ON nss.parichaya_patra (affiliated_organization_pk)
    WHERE affiliated_organization_pk IS NOT NULL;

CREATE UNIQUE INDEX uq_pp_active_per_member
    ON nss.parichaya_patra (sangha_sevi_pk)
    WHERE status = 'ACTIVE';
```

Columns: `parichaya_patra_pk`; `sangha_sevi_pk UUID NOT NULL` — FK; `document_number VARCHAR(30)
NOT NULL` — **the** Tier 3 identity column, format `<seq>/<FY start>/<FY end>` (e.g.
`345/2026/2027`); `issue_date DATE NOT NULL`; `valid_from`/`valid_to DATE NOT NULL` — financial
year validity (1 April–31 March), both required (unlike `sangha_sevi.renewal_due_date`, a card's
validity window is known at issuance); `status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'` —
`ACTIVE`/`EXPIRED`/`CANCELLED`/`REPLACED`; then the two **card-snapshot** columns, called out with
their own comment block in the DDL: `affiliated_organization_pk UUID NULL` and
`local_sakha_erp_id VARCHAR(30) NULL` — point-in-time copies of what was printed on that year's
card, both nullable because a snapshot could in principle be recorded without a resolved
Sakha/ID; `document_reference VARCHAR(255) NULL`; `remarks TEXT NULL`; two-column audit block
(mutable — a card's `status` transitions in place, e.g. `ACTIVE` → `EXPIRED`).

Constraints: `fk_pp_sevi` (plain); `fk_pp_affiliated_org` — a FK on a nullable column (no explicit
`LEFT`-anything at the DDL level, but this is what makes the corresponding API JOIN a `LEFT
JOIN`); `chk_pp_validity_range CHECK (valid_to > valid_from)` — strict `>`, same as the renewal
history table; `chk_pp_status` — the shared four-value document-status enum
(`ACTIVE`/`EXPIRED`/`CANCELLED`/`REPLACED`) reused verbatim by `anumati_patra` below;
`uq_pp_document_number UNIQUE (document_number)` — Kendra Numbers are globally unique.

Indexes: `sangha_sevi_pk`, `status`, composite `(valid_from, valid_to)`; `idx_pp_affiliated_org` —
a **partial** index (`WHERE affiliated_organization_pk IS NOT NULL`), skipping the nullable
snapshot column's null entries; and `uq_pp_active_per_member` — a **partial unique index**
(`WHERE status = 'ACTIVE'`) enforcing "at most one `ACTIVE` Parichaya Patra per member," the same
partial-unique-index idiom as `uq_mem_sakha_aff_active`.

---

### database/ddl/05_membership/10_parichaya_patra_history.sql

> **Real, implemented DDL.** Depth 4 (depends on `parichaya_patra`).

**Requirement**

Defines `nss.parichaya_patra_history` — the change log for a `parichaya_patra` row
(issued/renewed/expired/cancelled/replaced). Historical records are never deleted — the second
instance of the "current state + history" pairing pattern in this module, this time recording
the *events* that changed a document's status rather than the status itself.

**Line-by-line explanation**

```sql
CREATE TABLE nss.parichaya_patra_history
(
    parichaya_patra_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    parichaya_patra_pk UUID NOT NULL,

    change_type VARCHAR(20) NOT NULL,

    change_date DATE NOT NULL,

    previous_status VARCHAR(20) NULL,

    new_status VARCHAR(20) NOT NULL,

    document_reference VARCHAR(255) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_pp_hist_pp
        FOREIGN KEY (parichaya_patra_pk)
        REFERENCES nss.parichaya_patra (parichaya_patra_pk),

    CONSTRAINT chk_pp_hist_change_type
        CHECK
        (
            change_type IN ('ISSUED', 'RENEWED', 'EXPIRED', 'CANCELLED', 'REPLACED')
        ),

    CONSTRAINT chk_pp_hist_new_status
        CHECK
        (
            new_status IN ('ACTIVE', 'EXPIRED', 'CANCELLED', 'REPLACED')
        )
);

CREATE INDEX idx_pp_hist_pp ON nss.parichaya_patra_history (parichaya_patra_pk);
CREATE INDEX idx_pp_hist_change_date ON nss.parichaya_patra_history (change_date);
```

Columns: `parichaya_patra_history_pk`; `parichaya_patra_pk UUID NOT NULL` — FK to the parent card
(Depth 4 — one level deeper than `parichaya_patra` itself, since it depends on a table that
itself depends on `sangha_sevi`); `change_type VARCHAR(20) NOT NULL` —
`ISSUED`/`RENEWED`/`EXPIRED`/`CANCELLED`/`REPLACED`, a five-value enum one step more granular
than the parent table's four-value `status`; `change_date DATE NOT NULL`; `previous_status
VARCHAR(20) NULL` — nullable because the very first `ISSUED` event has no prior status;
`new_status VARCHAR(20) NOT NULL` — reuses the parent's four-value status enum; `document_reference
VARCHAR(255) NULL`; `remarks TEXT NULL`; single-column audit block (`created_at` only —
append-only).

Constraints: one FK; `chk_pp_hist_change_type` (5-value enum) and `chk_pp_hist_new_status`
(4-value enum, matching the parent table's `chk_pp_status`) — two separate CHECKs distinguishing
"what kind of event happened" from "what status resulted."

Indexes: `parichaya_patra_pk`, `change_date`.

---

### database/ddl/05_membership/11_anumati_patra.sql

> **Real, implemented DDL.** Depth 3 (depends on `sangha_sevi`).

**Requirement**

Defines `nss.anumati_patra` — the Probationary member's credential ("Admit Card," Bye-Law
§B(a)), structurally near-identical to `parichaya_patra` but with **no Sakha-snapshot columns**
— it isn't tied to a specific Sakha the way the Identity Card is. Must be valid at least one
year before Regular enrolment (Bye-Law §B(b)(i)).

**Line-by-line explanation**

```sql
CREATE TABLE nss.anumati_patra
(
    anumati_patra_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    document_number VARCHAR(30) NOT NULL,

    issue_date DATE NOT NULL,

    valid_from DATE NOT NULL,

    valid_to DATE NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    document_reference VARCHAR(255) NULL,

    remarks TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_ap_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_ap_validity_range
        CHECK (valid_to > valid_from),

    CONSTRAINT chk_ap_status
        CHECK
        (
            status IN ('ACTIVE', 'EXPIRED', 'CANCELLED', 'REPLACED')
        ),

    CONSTRAINT uq_ap_document_number
        UNIQUE (document_number)
);

CREATE INDEX idx_ap_sevi ON nss.anumati_patra (sangha_sevi_pk);
CREATE INDEX idx_ap_status ON nss.anumati_patra (status);
CREATE INDEX idx_ap_valid_range ON nss.anumati_patra (valid_from, valid_to);

CREATE UNIQUE INDEX uq_ap_active_per_member
    ON nss.anumati_patra (sangha_sevi_pk)
    WHERE status = 'ACTIVE';
```

Column-for-column identical to `parichaya_patra` (§ above) minus the two card-snapshot columns
(`affiliated_organization_pk`, `local_sakha_erp_id`) and their corresponding FK/partial index —
same PK/FK/`document_number`/date-triple/`status`/`document_reference`/`remarks`/audit shape,
same `chk_ap_validity_range CHECK (valid_to > valid_from)`, same four-value `chk_ap_status` enum
reused verbatim from `parichaya_patra`'s `chk_pp_status`, same `uq_ap_document_number UNIQUE
(document_number)`, and the same partial-unique-index idiom for "one active document per member"
(`uq_ap_active_per_member`, mirroring `uq_pp_active_per_member`). The DDL comment on
`document_number` doesn't repeat the Kendra-Number format note `parichaya_patra` carries — Anumati
Patra document numbers follow their own `AP/<year>/<seq>` convention (see the seed data, e.g.
`AP/2025/42`), a module-internal numbering scheme rather than the Kendra-wide Parichaya Patra
sequence.

---

### database/ddl/05_membership/12_anumati_patra_history.sql

> **Real, implemented DDL.** Depth 4 (depends on `anumati_patra`).

**Requirement**

Defines `nss.anumati_patra_history` — the change log for an `anumati_patra` row, structurally
identical to `parichaya_patra_history`.

**Line-by-line explanation**

Column-for-column and constraint-for-constraint identical to `parichaya_patra_history` (§
above), with `anumati_patra_pk UUID NOT NULL` (FK `fk_ap_hist_ap → nss.anumati_patra`) in place
of `parichaya_patra_pk`: same `change_type`/`change_date`/`previous_status`/`new_status`/
`document_reference`/`remarks`/single-column-audit shape, same five-value `chk_ap_hist_change_type`
enum, same four-value `chk_ap_hist_new_status` enum, same two indexes
(`idx_ap_hist_ap`, `idx_ap_hist_change_date`). The Parichaya Patra / Anumati Patra pair and their
respective history tables are, by design, four tables built from two structural templates
(document + document-history), applied once to the Kendra-wide annual card and once to the
Probationary credential.

---

### database/seed/05_membership/01_tier4_verification_membership.sql

> **Real verification seed data** — unlike `database/seed/03_person/` (zero rows), this file
> populates 5 of the 12 Membership tables. Version 2.1.

**Requirement**

Seeds 5 `sangha_sevi` records (`SS1`–`SS5`) against 5 of the 8 test persons already seeded by
`database/seed/03_person/02_tier4_verification_persons.sql`, chosen specifically to exercise
every membership type, the full transfer workflow, and the Kumari-transition enrolment path —
not just to prove the schema accepts inserts. See `database/seed/05_membership/README.md` for
the full per-member breakdown; this section covers the SQL patterns the file uses.

**Line-by-line explanation**

```sql
INSERT INTO nss.sangha_sevi
    (sangha_sevi_id, person_pk, membership_type_master_data_pk,
     membership_status_master_data_pk, organization_pk,
     joining_date, renewal_due_date)
SELECT
    'SS1',
    p.person_pk,
    mt.master_data_pk,
    ms.master_data_pk,
    sakha.organization_pk,
    '2012-04-01',
    '2027-03-31'
FROM nss.person p
CROSS JOIN nss.master_data mt
JOIN nss.master_category mc_mt ON mc_mt.master_category_pk = mt.master_category_pk
CROSS JOIN nss.master_data ms
JOIN nss.master_category mc_ms ON mc_ms.master_category_pk = ms.master_category_pk
CROSS JOIN nss.organization sakha
WHERE p.person_id = 'P1'
  AND mc_mt.category_code = 'MEMBERSHIP_TYPE' AND mt.value_code = 'REGULAR'
  AND mc_ms.category_code = 'STATUS' AND ms.value_code = 'ACTIVE'
  AND sakha.organization_code = 'SKH1';
```

Every `INSERT` in this file (and every prior real-DDL seed file in this document) uses the same
`INSERT ... SELECT ... FROM <target> CROSS JOIN <lookup> WHERE <business-key filter>` idiom
rather than hardcoded UUIDs — a `CROSS JOIN` against `nss.master_data`/`nss.organization`/
`nss.person`/`nss.sangha_sevi`, narrowed to exactly one row by a `WHERE` clause matching business
identifiers (`person_id = 'P1'`, `organization_code = 'SKH1'`, `value_code = 'REGULAR'`), so the
seed file never needs to know or hardcode any actual UUID PK value. This particular statement
creates SS1 (Ramesh Mishra) as a REGULAR, ACTIVE member at SKH1, joined `2012-04-01`. The four
other `sangha_sevi` INSERTs (SS2–SS5) are structurally identical, varying only the literal ID,
target `person_id`, `value_code`s, `organization_code`, and dates.

**Section-by-section summary** (see `database/seed/05_membership/README.md` for the full member
breakdown):

| Section | Table(s) | Rows | Notable pattern |
|---|---|---|---|
| 1 | `sangha_sevi` | 5 (`SS1`–`SS5`) | One `INSERT...SELECT` per member, business-key-driven |
| 2 | `membership_sakha_affiliation` | 6 | SS3 gets **two** rows (`ESS1100` `ARCHIVED` at SKH1 with `effective_to` set, `CTC1` `ACTIVE` at SKH2 with `effective_to` omitted) — the transfer scenario in miniature |
| 3 | `parichaya_patra`, `anumati_patra` | 3 PP + 4 AP | PP only for SS1/SS3/SS4 (Regular/Associate); AP for SS1/SS2/SS3/SS5 (current or historical), none for SS4 (Associate) |
| 4 | `membership_transfer_history` | 1 | SS3's SKH1→SKH2 transfer, effective `2025-03-14` ("Dola Purnima 2025" per remarks) |
| 5 | `membership_journey_event` | 9 | Per-member lifecycle narrative, including SS3's `TRANSFER` event and SS5's Kumari-Transition-flavoured `MEMBERSHIP_CREATED` event |
| 6 | `membership_status_history` | 4 | One `ACTIVE`-since-joining row per member with a non-transfer origin story (SS1, SS3, SS4, SS5) |
| 7 | `membership_renewal_history` | 2 | SS1 and SS3, both FY 2026–2027 |

Total row count across the file: **5** `sangha_sevi` + **6** `membership_sakha_affiliation` +
**3** `parichaya_patra` + **4** `anumati_patra` + **1** `membership_transfer_history` + **9**
`membership_journey_event` + **4** `membership_status_history` + **2**
`membership_renewal_history` = **34 rows**, against **0 rows** in the remaining 5 Membership
tables (`membership_renewal_request`, `probationary_member_review`, `parichaya_patra_history`,
`anumati_patra_history`) — deliberate, not an oversight (see
`database/seed/05_membership/README.md`).

---

## 3. Cross-references

- `database/README.md` — canonical execution order, phase table, module implementation status,
  and the Two-Pass DDL Strategy (Pass 1 vs. Pass 2 audit-actor FKs) referenced throughout this
  document.
- `docs/03_Solution/architecture/DDL_CREATION_ORDER.md` (SOL-ARCH-010) — the frozen physical
  `CREATE TABLE` sequence and Depth/Seq# numbering cited in every DDL file's header comment.
- `docs/03_Solution/architecture/FK_DEPENDENCY_GRAPH.md` (SOL-ARCH-009) — the full table-to-table
  FK dependency graph that determines the Depth values used throughout this document.
- `docs/03_Solution/architecture/BOOTSTRAP_ARCHITECTURE.md` (SOL-ARCH-011) — the bootstrap
  sequence rationale, the `nss_db_owner`/`NSS_ERP_ADMIN` identity distinction, and the Two-Pass
  DDL Strategy's origin (the circular dependency between audited operations and the actor
  identity they require).
- `database/ddl/05_membership/README.md` and `database/seed/05_membership/README.md` — the
  Membership module's own table-design and seed-data references, including the "current state +
  history" pairing pattern and the three-tier identity split across `sangha_sevi`/
  `membership_sakha_affiliation`/`parichaya_patra` this document's per-table sections above
  describe at the DDL level.
