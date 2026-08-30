# database/seed/

Reference/lookup data, mirroring `database/ddl/` (run after the corresponding DDL).

| Folder | Contents |
|---|---|
| `01_foundation/` | **Implemented 2026-08-30** — 7 files: master categories (11), master data values (~40, across GENDER/MARITAL_STATUS/ADDRESS_TYPE/DOCUMENT_TYPE/MEMBERSHIP_TYPE/MEMBERSHIP_STATUS/RELATIONSHIP_TYPE), `id_sequence_master` rows (9, `PERSON` padded to 10 digits), country (5), state (112), district (~770, India only), system settings (5) |
| `03_person/` | Superseded prototype — `gender_master` / `marital_status_master` / `address_type_master` rows (seeds tables that don't exist in the new `master_data` pattern) |

No `02_organization/` seed folder exists — nothing to seed until `database/ddl/02_organization/`
is implemented.
