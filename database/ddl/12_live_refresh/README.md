# database/ddl/12_live_refresh/

Live-refresh change markers (cross-cutting, owner decision 2026-11-03; committed on `feature/tier6-governance`). Built as
Phase 11h of `02_build.sh`/`.ps1` and `render_build.sh`. The API side is `api/routers/live.py`
(`GET /api/v1/live/changes`); the page-side poller is `frontend/assets/js/live-refresh.js`.

| File | Contents |
|---|---|
| `01_live_change_marker.sql` | Table `nss.live_change_marker` (`table_name` PK, `change_seq`, `changed_at`) and the single global sequence `nss.live_change_seq`. Existence-gated (`run_ddl`/`Invoke-Ddl`). System table: no actor/soft-delete columns, excluded from `fn_audit_trigger()` (recorded in `CROSS_MODULE_PRINCIPLES.md` §7.1). |
| `02_live_change_triggers.sql` | Idempotent (`run_sql`/`Invoke-Sql`, runs on EVERY build): `nss.fn_live_change_marker()` (`SECURITY DEFINER`, pinned `search_path`, one UPSERT per statement) and the literal `watched` array of 55 tables that each get a statement-level AFTER INSERT/UPDATE/DELETE trigger; tables removed from the list lose their trigger on the next run, missing tables are skipped. |

Non-obvious wiring:

- A bump becomes visible at COMMIT and vanishes on rollback; there is no cursor, clock or look-back. The client compares `change_seq` per table.
- A list entry may be `'table!ignored1,ignored2'` (the listed columns are the ignored ones): the trigger is then `AFTER INSERT OR DELETE OR UPDATE OF <every other column>`. Only `user_account` uses it (login bookkeeping must not refresh every admin's Users page).
- The list must equal `LIVE_FEED_TABLES` in `api/routers/live.py` (`tests/api/test_live_changes.py::TestSqlParity` parses this file). Ballot tables (`election_vote*`) are deliberately absent.
- Add a table: edit the array here AND the Python whitelist, then re-run the build (or just this file on an existing DB).

Details: `docs/PROJECT_DOCUMENTATION.md` -> Key workflows -> Live refresh. Tests: `tests/db/test_live_change_marker.py`.
