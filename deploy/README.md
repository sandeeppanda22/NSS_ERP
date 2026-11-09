# deploy/

Environment templates for the two Render portals, DEV and PROD, each paired with its **own Neon project**
(decision 2026-11-09): separate roles, passwords and compute, so a dev build or hard rebuild can never touch
prod. The existing `nss_erp` database is PROD; DEV is a new empty `nss_erp` in a new project. Files ending
in `.env.example` are safe to commit; filled copies named `deploy/*.env` are gitignored and hold real
secrets — never commit them.

| File | Purpose |
|------|---------|
| `render-dev.env.example` | DEV portal ↔ Neon DEV project: first deploy `RUN_DB_BOOTSTRAP=true`, `DEBUG_MODE=true`, Swagger on |
| `render-prod.env.example` | PROD portal ↔ Neon PROD project (existing `nss_erp`): `RUN_DB_BOOTSTRAP=false`, `DISABLE_DOCS=true`, Aadhaar keys unset until GDR-011 clears |

Use: copy to `render-dev.env` / `render-prod.env`, fill in, paste into the Render dashboard
(Environment → Add from .env). Every secret (`DB_PASSWORD`, `DB_WRITE_PASSWORD`, `JWT_SECRET_KEY`, any
`AADHAAR_*`) must differ between the two files. The one-time Neon setup is in each file's header;
hard-rebuild steps are in the header of `render_build.sh`. `render.yaml` pins `DB_NAME=nss_erp`,
`DB_USER=nss_db_owner`, `DB_WRITE_USER` and `PYTHON_VERSION` for one service; the templates repeat them so a
dashboard-managed portal gets the same values. Full variable reference: `docs/PROJECT_DOCUMENTATION.md` →
Configuration.

## From-scratch runbook (per environment — repeat for DEV and PROD, each in its own Neon project)

1. **Neon:** delete the old project (if any); create a new project in the region nearest the Render service
   (e.g. AWS ap-southeast-1). Do not use the default `neondb_owner`. In the **console**: Roles → New role
   `nss_db_owner` (copy its password into `DB_PASSWORD`), then Databases → New database `nss_erp` with owner
   `nss_db_owner`. Then, in SQL connected **as `nss_db_owner`** to `nss_erp`, run `deploy/neon-setup.sql.example`
   (creates `nss_db_backend` and `nss_db_writer` and grants CONNECT). Connection details: untick "Pooled
   connection" and copy the host (`ep-….aws.neon.tech`, no `-pooler`) into `DB_HOST`.
2. **Secrets** (run locally, never reuse between environments):
   `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` for `DB_PASSWORD`-style passwords (or use Neon's),
   `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` for `JWT_SECRET_KEY`.
3. **Render:** create the web service from the repo (build `./render_build.sh`, start
   `uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2`, as in `render.yaml`); paste the filled
   `deploy/render-<env>.env`; set `CORS_ORIGINS` to the service's own URL. First deploy: `RUN_DB_BOOTSTRAP=true`.
4. **Deploy and read the log:** every phase prints `[OK]`/`[SKIP]`; `[FAIL]` stops the build. Phase 13 seeds the admin.
5. **Then** set `RUN_DB_BOOTSTRAP=false` (this triggers a harmless redeploy), log in at `/login` as `SS1` /
   `Admin@123`, and change the password immediately.
6. **Validate (optional):** `PGSSLMODE=require ./database/scripts/03_validate.sh nss_erp nss_db_owner <DB_HOST> 5432`.
