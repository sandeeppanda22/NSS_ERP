# database/

Hand-written PostgreSQL DDL and seed data — the "Database First" track of the project. This is
**not currently consumed by the Django app** in `backend/`; it's an independent, more detailed
schema design that the Django ORM models don't yet read from or write to (see
`docs/PROJECT_DOCUMENTATION.md` → Architecture/Gotchas).

## `ddl/` (run in this order)

- `01_foundation/` — `01_extensions.sql` (`pgcrypto`), `02_id_sequence_master.sql` (business-ID
  counter registry: `PERSON`/`SANGHA_SEVI`/`ORGANIZATION`/`FAMILY` prefixes — no increment
  logic implemented yet, pure config), `03_location_master_tables.sql` (country → state/province
  → district/region → city/village, plus a postal-code map table).
- `02_organization/` — **4 files, all 0 bytes.** Fully designed in
  `docs/03_Solution/modules/organization/` but not implemented here yet.
- `03_person/` — `01_person_master_tables.sql` (`gender_master`, `marital_status_master`,
  `address_type_master`), `02_person.sql` (`person`, incl. the contact-info CHECK constraints),
  `03_person_address.sql` (`person_address`, incl. the one-primary-address partial unique
  index). Fully implemented, matching `docs/03_Solution/modules/person/`.

## `seed/`

Mirrors `ddl/` — reference/lookup data only (4 `id_sequence_master` rows, 5 countries, and the
person master-table values). No `02_organization/` seed folder exists (nothing to seed yet).

## Naming convention

Internal UUID surrogate keys: `<entity>_pk`. Business/external identifiers: `<entity>_code`
(never `_id`) — e.g. `person_code`, `country_code`, `sequence_code`.
