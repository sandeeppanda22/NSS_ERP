# database/seed/11_assets_property/

| File | Contents |
|---|---|
| `01_assets_property_reference_data_patch.sql` | **Idempotent patch** (`run_sql`/`Invoke-Sql` on every build, `ON CONFLICT DO NOTHING`; build Phase 11g): `id_sequence_master` rows `PROPERTY` (prefix `PROP`) and `ASSET` (prefix `AST`) → `PROP1…` / `AST1…` unpadded; 7 `master_category` rows (`PROPERTY_TYPE`, `ASSET_TYPE`, `CUSTODIANSHIP_END_REASON`, `STATUTORY_OBLIGATION_TYPE`, `MAINTENANCE_TYPE`, `ASSET_PROPERTY_DOCUMENT_RELATIONSHIP`, `ACQUISITION_METHOD`) and 38 `master_data` values (the PENDING sets are *candidates* and stay admin-extendable via `POST /api/v1/foundation/master-data`; the owner accepted them as seeded on 2026-11-03). 2026-11-03 additions: category `ACQUISITION_METHOD` (`PURCHASE`, `DONATION` — source-grounded — plus candidates `GIFT`, `BEQUEST`, `TRANSFER_IN`, `CONSTRUCTION`, `OTHER`; GDR-010 §2E) and the `CUSTODIANSHIP_END_REASON` values `DISPOSED`, `RETIRED` (reserved for the terminal event; GDR-010 §2F). `../../ddl/11_assets_property/12_assets_property_terminal_custody_patch.sql` must run after this file. |

This is a patch rather than an edit of `seed/01_foundation/*` because the Foundation seeds are existence-gated by
`02_build.sh`/`.ps1`/`render_build.sh` and never re-run on an existing database (the module therefore has a single
source for its reference data). The module's RBAC lives in `../00_bootstrap/05_assets_property_permissions_patch.sql`.
Authority: SOL-AP-005 §7–§15, GDR-010.
