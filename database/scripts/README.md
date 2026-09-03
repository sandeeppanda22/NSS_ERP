# database/scripts/

Executable build/validate scripts for the raw-SQL DDL track. Run from the repository root.
Replaces the old repo-root `validate_foundation.sh` (deleted — was Foundation-only).

| File | Run as | Purpose |
|---|---|---|
| `00_create_database.sql` | PostgreSQL superuser (e.g. `postgres`) | One-time: creates the `nss_erp` database and the `nss_admin`/`app_backend` roles. Idempotent. |
| `01_build.sh` | `nss_admin` | Runs all currently-implemented DDL + seed files (Bootstrap RBAC → Foundation → Organization) in phase order. Not idempotent — drop/recreate the database for a clean rebuild. |
| `02_validate.sh` | `nss_admin` | Post-build checks: table existence, row counts, unique-column duplicates, FK integrity. Run after `01_build.sh`; does not execute any DDL/seed itself. |

All three accept the same optional positional args: `DB_NAME DB_USER DB_HOST DB_PORT`
(defaults `nss_erp nss_admin localhost 5432`).

See `database/README.md` → "Scripts" for full usage examples and the per-module validation
checklist.
