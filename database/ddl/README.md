# database/ddl/

Hand-written PostgreSQL DDL, run in numeric folder order (driven by `database/scripts/02_build.sh`/`.ps1`).
69 tables in total (counted from `CREATE TABLE` statements, per-folder breakdown below).

| Folder | Status |
|---|---|
| `00_bootstrap/` | **Implemented** — 3 tables: `role_master`, `permission_master`, `role_permission` (RBAC definitions, created before Foundation since they have no FK dependencies) |
| `01_foundation/` | **Implemented** — 15 tables: master category/data, system settings, ID sequence registry, location hierarchy (country/state/district/city_village/postal_code/post_office — the last four member-writable), document registry, field change log (12 tables in files 02–13), `16_festival_master.sql`/`17_festival_calendar_date.sql`, plus `14_system_event_log.sql` (centralized audit trail, Tier 5). `15_audit_trigger.sql` creates no table — it defines `fn_audit_trigger()` and attaches it to every other `nss.*` table, so it must run last in the whole build (Phase 14) |
| `02_organization/` | **Implemented** — 1 table: `organization` (self-referencing hierarchy, address inline) plus 2 triggers (`04_organization_address_restriction_trigger.sql`, `05_organization_kumari_sevak_uniqueness_trigger.sql`). Type/status masters retired in favor of Foundation's generic `master_category`/`master_data` (categories `ORGANIZATION_TYPE`, `STATUS`) |
| `03_person/` | **Implemented** — 2 tables: `person` (32 columns, incl. audit/soft-delete columns) and `person_address`, both resolving gender/marital status/blood group/address type via Foundation's `master_category`/`master_data` pattern. `01_person_master_tables.sql` is superseded and not run (see `database/README.md` Superseded Artifacts) |
| `04_family/` | **Implemented** — 6 tables: `family_group`, `family_relationship`, `family_head_history`, `family_transition_history`, `family_link`, `family_admin` (new, Tier 5), plus `07_family_move_transition_guard.sql` (deferred constraint trigger, no table) |
| `05_membership/` | **Implemented** — 16 tables (adds `sakha_local_number_counter`, `membership_change_request`): `sangha_sevi` and its status/renewal/transfer/affiliation/journey/review/credential history tables, `darshak_attendance_registration` and `credential_sequence_counter` (both new, Tier 5), plus `14_sakha_only_membership_trigger.sql` (MBR-038A, no table) |
| `06_authentication/` | **Implemented (Tier 5, v0.11.0)** — 5 tables: `user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session` |
| `07_administration/` | **Implemented (Tier 5, v0.11.0)** — 2 tables: `user_role`, `admin_scope` |
| `08_governance/` | **Implemented (Tier 6)** — 10 tables: `body_type_master`, `position_master`, `body_master`, `body_member_assignment`, `acting_position_assignment`, `election`, `election_nomination`, `election_vote`, `election_result`, `election_vote_participation`; plus `fn_block_update()` immutability triggers on votes/participation |
| `09_correspondence/` | **Implemented (Tier 6)** — 5 tables: `correspondence`, `correspondence_document`, `correspondence_finance_reference`, `correspondence_sequence_counter`, `correspondence_approval_step`. Administration-owned capability (CORR-DECISION-003); moved from Tier 5 to Tier 6 (owner-confirmed 2026-10-16) since Tier 5 (v0.11.0) already shipped without it. `correspondence_finance_reference.financial_transaction_pk` has no FK yet — deferred to Pass 2 until Finance (Tier 12) exists |
| `10_attendance/` | **Implemented (Tier 6, uncommitted)** — 4 tables: `weekly_sangha_puja`, `weekly_sangha_puja_attendance`, `attendance_exception`, `attendance_review`; see its README |

Tables per folder: 3 + 15 + 1 + 2 + 6 + 16 + 5 + 2 + 10 + 5 + 4 = 69.

Build phase numbers differ from folder numbers (Foundation's `14`/`15` run as Phase 14, after
everything else; Authentication is Phase 10, Administration Phase 11) — see
`database/scripts/README.md` for the authoritative phase order.

See `database/README.md` and `docs/PROJECT_DOCUMENTATION.md` for the full schema breakdown.
