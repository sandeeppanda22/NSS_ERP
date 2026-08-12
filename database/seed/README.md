# database/seed/

Reference/lookup data, mirroring `database/ddl/` (run after the corresponding DDL).

| Folder | Contents |
|---|---|
| `01_foundation/` | `id_sequence_master` rows, country seed data |
| `03_person/` | `gender_master` / `marital_status_master` / `address_type_master` rows |

No `02_organization/` seed folder exists — nothing to seed until `database/ddl/02_organization/`
is implemented.
