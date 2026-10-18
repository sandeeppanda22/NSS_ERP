# database/ddl/09_correspondence/

Correspondence Register DDL — 4 tables (Tier 6, uncommitted). Administration-owned capability
(CORR-DECISION-003, SOL-ADMIN-009); moved from Tier 5 to Tier 6 after v0.11.0 shipped without it.
Built as Phase 11d of `02_build.sh`/`.ps1` and `render_build.sh` (after Governance, before the
Phase 12 writer grant and Phase 14 audit trigger, so both cover these tables).

| File | Table | Notes |
|---|---|---|
| `01_correspondence.sql` | `correspondence` | Depth 4. FKs to `person`, `organization`, `master_data` (medium/status). Sender/recipient use a compound CHECK: exactly one of person FK / organization FK / external free text. `reference_number` is application-generated (`<ORG_SHORT_CODE>/{IN\|OUT}/YYYY-YY/NNN`, CORR-EXT-001), immutable. Soft delete only (CORR-BR-015) |
| `02_correspondence_document.sql` | `correspondence_document` | Depth 5. FKs to `correspondence`, `document_master`; `document_purpose` CHECK (ORIGINAL/RESPONSE/ATTACHMENT/SUPPORTING) |
| `03_correspondence_finance_reference.sql` | `correspondence_finance_reference` | `relationship_type` is a `master_data` FK (category `CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE`, seeded in `seed/01_foundation/`). `financial_transaction_pk` has no FK yet — deferred until Finance (Tier 12) exists |
| `04_correspondence_sequence_counter.sql` | `correspondence_sequence_counter` | Depth 1. FK to `organization` only. One row per (`register_organization_pk`, `direction`, `financial_year_start`); backs `api/helpers.py::next_correspondence_reference_number()`. Mirrors `database/ddl/05_membership/15_credential_sequence_counter.sql`'s FY-scoped counter shape (CORR-EXT-001 §3.2) |

API: `api/routers/correspondence.py` + `api/schemas/correspondence.py`, registered in `api/main.py`.
Reference-number prefix requires the register organization's `organization.short_code` to be set
(only Kendra ships one seeded — `database/seed/02_organization/03_organization.sql`); registering
correspondence under an organization with no `short_code` is rejected with a 422 pending that
org's `short_code` being assigned via the admin UI. Audit-actor FKs (`*_by_sangha_sevi_pk`) are
nullable and unconstrained (project-wide Pass 2). Tests: `tests/db/test_correspondence_schema.py` (schema only); no `tests/api/` file for `correspondence.py` yet.

Folder index: [`../README.md`](../README.md). Design: `docs/03_Solution/modules/administration/`.
