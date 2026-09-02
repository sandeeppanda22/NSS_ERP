# database/seed/

Reference/lookup data, mirroring `database/ddl/` (run after the corresponding DDL).

| Folder | Contents |
|---|---|
| `00_bootstrap/` | **Partial** — `role_master`: 8 roles seeded; `permission_master`/`role_permission`: empty, blocked on the permission catalogue being frozen |
| `01_foundation/` | **Implemented** — 7 files: master categories (11), master data values (~40, across GENDER/MARITAL_STATUS/ADDRESS_TYPE/DOCUMENT_TYPE/MEMBERSHIP_TYPE/MEMBERSHIP_STATUS/RELATIONSHIP_TYPE), `id_sequence_master` rows (9, `PERSON` padded to 10 digits), country (5), state (112), district (~770, India only), system settings (5) |
| `02_organization/` | **Implemented** — type masters (8 organization types) + status master + 3 unique named organizations (Kendra, Nilachala Kutira, Smruti Mandira) |
| `03_person/` | Superseded prototype — `gender_master` / `marital_status_master` / `address_type_master` rows (seeds tables that don't exist in the new `master_data` pattern) |
