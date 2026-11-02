# scripts/

Top-level, repo-root operational Python scripts — distinct from `database/scripts/` (SQL/shell
bootstrap scripts). Added in Tier 5 (released in v0.11.0).

| File | Purpose |
|---|---|
| `backfill_sibling_links.py` | One-time backfill (Tier 6 follow-up): inserts the missing `SIBLING_OF` `family_link` edge for BROTHER/SISTER `family_relationship` rows created before `family.py` started writing it. Run `python3 scripts/backfill_sibling_links.py --dry-run` first (report only), then without the flag; needs the widened `chk_family_link_type` CHECK from `database/ddl/04_family/05_family_link.sql` (full rebuild) and `api/.env` write credentials. |
| `bootstrap_admin.py` | Seeds the NSS Admin superuser (`P1`/`SS1`, `NSS_ERP_ADMIN` role, `NSS-WIDE` scope). Run as `python3 scripts/bootstrap_admin.py` (optionally `--password <pw>`; default `Admin@123`) from the repository root, after the database has been built through Phase 12 (Administration DDL + `nss_db_writer` grant). |

How it works: it hashes the password with `api.services.auth_service.hash_password` (Argon2),
reads `database/seed/04_admin/01_admin_bootstrap.sql` (the single source of truth for what the
account looks like — the script deliberately contains no SQL of its own), and executes that
multi-statement file in **one transaction** through a connection from
`api.database.get_write_pool()`, binding the one `%(password_hash)s` placeholder. It rolls back
and exits 1 on any error, or if the seed file is missing. It needs `api/.env` with working
`DB_WRITE_USER`/`DB_WRITE_PASSWORD` (plus the standard DB settings); it puts the repo root on
`sys.path` itself (via `Path(__file__).resolve().parent.parent`) so the `api.*` imports resolve.

This exists as Python (not plain `psql -f ...`) because `nss.user_account.password_hash` needs a
runtime-generated Argon2 hash — there is no SQL-only way to produce one, and the project's "no
hardcoded credentials" rule means the hash cannot be pre-computed into a seed file either.

Idempotency: the seed's INSERTs are all `WHERE NOT EXISTS`-guarded, so re-running does not create
duplicates and **does not reset an existing admin's password** (the `user_account` insert is
skipped if `P1` already has an account); only the `PERSON`/`SANGHA_SEVI` `id_sequence_master`
counters are nudged up to at least 1.

Called automatically as Phase 13 of `database/scripts/02_build.sh`/`.ps1` and `render_build.sh`
(a failure there is counted by the `02_build` scripts, which still run Phase 14 and then exit 1,
but only warns in `render_build.sh`) — you only need to run it by hand when bootstrapping a
database outside those scripts (e.g. re-seeding a dropped-and-recreated local dev DB). The
`__pycache__/` folder beside it is generated and untracked.
