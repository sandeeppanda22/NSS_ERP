# database/ddl/01_foundation/

- `01_extensions.sql` — enables the `pgcrypto` extension (backs `gen_random_uuid()` used as the
  default for every `_pk` column in the schema).
- `02_id_sequence_master.sql` — `id_sequence_master` table: a registry of business-ID counters
  (`sequence_code`, `prefix`, `current_value`, `padding_length`). No SQL function/trigger
  implements the increment/formatting logic yet — see
  `docs/PROJECT_DOCUMENTATION.md` → Key workflows.
- `03_location_master_tables.sql` — global location hierarchy: `country_master` →
  `state_province_master` → `district_region_master` → `city_village_master`, plus
  `postal_code_master` and the `city_village_postal_code_map` junction table.
