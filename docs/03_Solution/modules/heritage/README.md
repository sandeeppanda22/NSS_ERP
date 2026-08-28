# NSS ERP Founder & Heritage Module

Status: DRAFT — SOURCE ALIGNED (Solution design complete, v1.0.0). SQL implementation not
started for 7 of 8 designed tables — see Note below.

Complete 5-document Solution-level design set, following the same
`01_module_overview` / `02_erd` / `03_lifecycle` / `04_business_rules` / `05_table_design`
pattern used by `docs/03_Solution/modules/organization/`, `person/`, `membership/`, etc.

## Documents

- `01_founder_heritage_module_overview.md` (SOL-HER-001) — module purpose and scope
- `02_founder_heritage_erd.md` — entity relationship design
- `03_founder_heritage_lifecycle.md` — lifecycle states
- `04_founder_heritage_business_rules.md` — HER-001–HER-100
- `05_founder_heritage_table_design.md` — logical table design, 8 tables

## Tables designed (8)

`founder_master` (single immutable record — Founder = Swami Nigamananda Paramahansa Dev),
`founder_teaching`, `nss_objective_master`, `nss_historical_milestone`, `nss_publication`
(v1.1 — mandatory language, free/donation/fixed-price models, physical+digital coexistence,
multiple editions, digitization support), `historical_office_bearer`, `publication_type_master`,
`publication_language_master`.

## Note — design/code gap

`backend/heritage/` (see `backend/heritage/README.md`) currently implements **only**
`founder_master`, via the `Founder` singleton model (`backend/heritage/models.py`) with no
`urls.py`/views. The other 7 tables designed here have no backend representation yet. Future
entities beyond this frozen scope are explicitly excluded per the business rules document.
