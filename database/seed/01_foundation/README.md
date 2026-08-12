# database/seed/01_foundation/

- `01_id_sequence_master.sql` — 4 rows: `PERSON`→`P`, `SANGHA_SEVI`→`SS`, `ORGANIZATION`→`ORG`,
  `FAMILY`→`F`, all starting at `current_value = 0`, `padding_length = 8`.
- `02_location_master_seed.sql` — 5 rows in `country_master`: India, United States, United
  Kingdom, Australia, Canada. No seed data exists yet for state/district/city/postal-code
  tables.
