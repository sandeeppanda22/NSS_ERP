# database/ddl/

Hand-written PostgreSQL DDL, run in numeric folder order.

| Folder | Status |
|---|---|
| `01_foundation/` | **Implemented 2026-08-30** (Foundation Vertical Slice) — 12 tables: extensions, master category/data, system settings, ID sequence registry, location hierarchy (country/state/district/city_village/postal_code + mapping), document registry, field change log |
| `02_organization/` | **Not implemented** — 4 files, all 0 bytes |
| `03_person/` | **Superseded prototype** — uses per-domain masters (`gender_master`, etc.) instead of the `master_data` pattern now implemented in `01_foundation/`; will be rewritten (see `feature/person-ddl`, `database/README.md` Superseded Artifacts) |

See `database/README.md` and `docs/PROJECT_DOCUMENTATION.md` for the full schema breakdown.
