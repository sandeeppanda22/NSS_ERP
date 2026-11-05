# database/ddl/13_audit_actor_fk/

Audit-actor foreign keys (cross-cutting, owner decision 2026-11-04). Built as Phase 13c of `02_build.sh`/`.ps1` and
`render_build.sh` (after the Phase 13 admin bootstrap, before the Phase 14 audit trigger, so every table already exists).

| File | Contents |
|---|---|
| `01_audit_actor_fk_patch.sql` | No table. Idempotent (`run_sql`/`Invoke-Sql`, every build), catalog-driven: for every base-table column in schema `nss` named `*_by_sangha_sevi_pk` without an existing FK to `nss.sangha_sevi`, adds `fk_<table>_<column>` (name truncated with an md5 suffix beyond 63 characters) as `NOT VALID`, then tries `VALIDATE`; a validation failure or a column of the wrong type is only a WARNING. |

Non-obvious wiring:

- New tables just declare a plain nullable UUID `*_by_sangha_sevi_pk`; never hand-write the FK or edit the patch. A non-Sangha-Sevi actor must write NULL (a bogus uuid is rejected for new/updated rows).
- `NOT VALID` means historical rows are never scanned, so dangling legacy values cannot break a rebuild; find them with the diagnostic SELECT in `database/scripts/README.md` (Phase 13c). `03_validate` WARNs on missing or still-NOT-VALID actor FKs.
- Existing FKs (e.g. `05_membership/16_foundation_audit_fk.sql`) are left alone; `system_event_log.actor_sangha_sevi_pk` is not covered.

Tests: `tests/db/test_audit_actor_fk.py`. Details: `docs/PROJECT_DOCUMENTATION.md` -> Conventions & gotchas.
