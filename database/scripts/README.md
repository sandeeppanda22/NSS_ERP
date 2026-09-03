# database/scripts/

Executable bootstrap/build/validate scripts for the raw-SQL DDL track.
Run from the repository root. Replaces the old repo-root
`validate_foundation.sh` (deleted — was Foundation-only).

## Execution Order

```
Step 1:  psql -U postgres -d postgres  -f database/scripts/00_create_database.sql
Step 2:  psql -U postgres -d nss_erp   -f database/scripts/01_extensions.sql
Step 3:  ./database/scripts/02_build.sh
Step 4:  ./database/scripts/03_validate.sh
```

## Script Reference

| File | Run as | Target DB | Purpose |
|---|---|---|---|
| `00_create_database.sql` | superuser (`postgres`) | `postgres` | Creates `nss_erp` database, `nss_admin`/`app_backend` roles, installs `dblink`. Fully idempotent. |
| `01_extensions.sql` | superuser (`postgres`) | `nss_erp` | Installs `pgcrypto`, `pg_trgm`, `btree_gin`, `postgis`. Idempotent. |
| `02_build.sh` | `nss_admin` | `nss_erp` | Runs all implemented DDL + seed (Bootstrap RBAC → Foundation → Organization). Not idempotent — drop/recreate DB for clean rebuild. |
| `03_validate.sh` | `nss_admin` | `nss_erp` | Post-build checks: table existence, row counts, unique constraints, FK integrity. Run after `02_build.sh`; does not execute any DDL/seed. |

`02_build.sh` and `03_validate.sh` accept optional positional args:
`DB_NAME DB_USER DB_HOST DB_PORT` (defaults: `nss_erp nss_admin localhost 5432`).

See `database/README.md` → "Scripts" for full usage examples and the
per-module validation checklist.
