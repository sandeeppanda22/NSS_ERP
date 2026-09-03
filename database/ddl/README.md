# database/ddl/

Hand-written PostgreSQL DDL, run in numeric folder order.

| Folder | Status |
|---|---|
| `00_bootstrap/` | **Implemented** — 3 tables: `role_master`, `permission_master`, `role_permission` (RBAC definitions, created before Foundation since they have no FK dependencies) |
| `01_foundation/` | **Implemented** — 12 tables: extensions, master category/data, system settings, ID sequence registry, location hierarchy (country/state/district/city_village/postal_code + mapping), document registry, field change log |
| `02_organization/` | **Implemented** — 3 tables: `organization_type_master`, `organization_status_master`, `organization` (self-referencing hierarchy, address inline) |
| `03_person/` | **Superseded prototype** — uses per-domain masters (`gender_master`, etc.) instead of the `master_data` pattern now implemented in `01_foundation/`; will be rewritten (see `feature/person-ddl`, `database/README.md` Superseded Artifacts) |

See `database/README.md` and `docs/PROJECT_DOCUMENTATION.md` for the full schema breakdown.
