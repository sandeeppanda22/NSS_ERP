# database/ddl/03_person/

**Implemented** — 2 tables: `person` (33 columns, incl. 7 audit/soft-delete columns) and `person_address`. Both follow the
Foundation `master_category`/`master_data` pattern: gender, marital status, blood group, and
emergency relationship resolve via `master_data` (categories `GENDER`, `MARITAL_STATUS`,
`BLOOD_GROUP`), and `person_address.address_type_master_data_pk` resolves via `master_data`
category `ADDRESS_TYPE`.

- (The former `01_person_master_tables.sql` stub — superseded by Foundation `master_data` — has been deleted.)
- `02_person.sql` — `person` table, incl. the `chk_person_contact_required` and
  `chk_person_mobile_pair` CHECK constraints. Audit-actor FKs
  (`created_by_sangha_sevi_pk`/etc.) are nullable columns in this pass; their FK constraints
  are deferred to Pass 2 (after `sangha_sevi` exists).
  The three `aadhaar_*` columns (`aadhaar_encrypted` BYTEA, `aadhaar_hash`, `aadhaar_last4`; GDR-011) are guarded by
  `chk_person_aadhaar_consistency` (all NULL or all set), `chk_person_aadhaar_last4_format` and the partial unique index
  `uq_person_aadhaar_hash`; only `api/services/aadhaar_service.py::set_person_aadhaar()` writes them.
- `03_person_address.sql` — `person_address` table, incl. the partial unique index
  (`uq_person_primary_address`) enforcing one primary address per person.

Matches `docs/03_Solution/modules/person/05_person_table_design.md` closely — see that doc for
the full design rationale. See also `docs/PROJECT_DOCUMENTATION.md` for the tier-by-tier plan.
