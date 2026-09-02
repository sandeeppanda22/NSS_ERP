# database/ddl/03_person/

> **Superseded prototype** — uses per-domain master tables (`gender_master`, etc.) instead of the
> generic `master_category`/`master_data` pattern implemented in `database/ddl/01_foundation/`.
> Will be rewritten against that pattern (see `feature/person-ddl`, `database/README.md`
> "Superseded Artifacts"). Described below for reference only — don't build on it.

- `01_person_master_tables.sql` — `gender_master`, `marital_status_master`, `address_type_master`.
- `02_person.sql` — `person` table, incl. the `chk_person_contact_required` and
  `chk_person_mobile_pair` CHECK constraints.
- `03_person_address.sql` — `person_address` table, incl. the partial unique index
  (`uq_person_primary_address`) enforcing one primary address per person.

Matches `docs/03_Solution/modules/person/04_person_table_design.md` closely — see that doc for
the full design rationale.
