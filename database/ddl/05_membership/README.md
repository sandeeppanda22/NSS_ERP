# database/ddl/05_membership/

Membership Module DDL — 16 tables (Depth 2–4) per SOL-MEM-005, SOL-MEM-003, plus (for
`darshak_attendance_registration`) SOL-MEM-006, and one enforcement-trigger file. The 13th table
(`darshak_attendance_registration`, v1.1 in Tier 6 adds `initiated_by_sangha_sevi_pk` + `request_source` — `MEMBER_SELF`/`ADMIN_AUTOMATIC_ENTRY`, DAR-009) and 14th (`credential_sequence_counter`) are Tier 5
additions (released in v0.11.0). `16_foundation_audit_fk.sql` is a Pass-2-style `ALTER TABLE` file (no table) that lives
here because it needs `sangha_sevi`. The 15th (`sakha_local_number_counter`) and 16th
(`membership_change_request`) tables are Tier 6 additions backing the Sakha Transfer / Apply for
Darshak workflow (MBR-048, MBR-049).

Authority: SOL-MEM-005 v1.0 (Physical Table Design), SOL-MEM-003 (Business Rules), MBR-001
through MBR-049 (business-rule identifiers cited in table comments); SOL-MEM-006 for
`darshak_attendance_registration`.

> **Design-doc status note:** `docs/03_Solution/modules/membership/README.md` still reads
> "Status: DRAFT — full Solution design complete, **not yet implemented in SQL**" / "SQL
> Implementation Not Started." That status predates this DDL — all 14 tables below are real,
> implemented, and executed by `database/scripts/02_build.sh`/`02_build.ps1` (Phase 7). The module design
> docs themselves are out of scope for this pass (a separate governance/design update); treat the
> tables in this folder, not that README, as the current source of truth for what exists in the
> database.

## DDL Execution Order

Execute AFTER Foundation, Organization, and Person DDL (`database/ddl/01_foundation/`,
`02_organization/`, `03_person/`) — every table here has at least one FK into `person`,
`master_data`, or `organization`, and most depend on `nss.sangha_sevi` itself (Depth 2).

| # | File | Table | Depth | Depends on |
|--:|------|-------|------:|------------|
| 01 | `01_sangha_sevi.sql` | `sangha_sevi` | 2 | `person`, `master_data` (×2), `organization` |
| 02 | `02_membership_status_history.sql` | `membership_status_history` | 3 | `sangha_sevi`, `master_data` |
| 03 | `03_membership_renewal_request.sql` | `membership_renewal_request` | 3 | `sangha_sevi` |
| 04 | `04_membership_renewal_history.sql` | `membership_renewal_history` | 3 | `sangha_sevi` |
| 05 | `05_membership_transfer_history.sql` | `membership_transfer_history` | 3 | `sangha_sevi`, `organization` (×2) |
| 06 | `06_membership_sakha_affiliation.sql` | `membership_sakha_affiliation` | 3 | `sangha_sevi`, `organization` |
| 07 | `07_membership_journey_event.sql` | `membership_journey_event` | 3 | `sangha_sevi` |
| 08 | `08_probationary_member_review.sql` | `probationary_member_review` | 3 | `sangha_sevi` |
| 09 | `09_parichaya_patra.sql` | `parichaya_patra` | 3 | `sangha_sevi`, `organization` |
| 10 | `10_parichaya_patra_history.sql` | `parichaya_patra_history` | 4 | `parichaya_patra` |
| 11 | `11_anumati_patra.sql` | `anumati_patra` | 3 | `sangha_sevi`, `organization` |
| 12 | `12_anumati_patra_history.sql` | `anumati_patra_history` | 4 | `anumati_patra` |
| 13 | `13_darshak_attendance_registration.sql` | `darshak_attendance_registration` | 3 | `sangha_sevi`, `organization` (×2) |
| 14 | `14_sakha_only_membership_trigger.sql` | *(no table — 2 BEFORE triggers, MBR-038A)* | — | `sangha_sevi`, `membership_sakha_affiliation`, `organization`, `master_data` |
| 15 | `15_credential_sequence_counter.sql` | `credential_sequence_counter` | 3 | `organization` |
| 16 | `16_foundation_audit_fk.sql` | *(no table — adds the `submitted_by_`/`reviewed_by_sangha_sevi_pk` FKs on Foundation `district`, `postal_code`, `post_office`, `city_village`; run as Phase 7b)* | — | `sangha_sevi` + the four Foundation tables |
| 17 | `17_sakha_local_number_counter.sql` | `sakha_local_number_counter` | 3 | `organization` |
| 18 | `18_membership_change_request.sql` | `membership_change_request` | 3 | `sangha_sevi`, `organization` (×2) |

## What Each Table Is For

- **`sangha_sevi`** — the member record itself. One row per membership, one membership per
  person (`UNIQUE (person_pk)` — "One Person = One Membership"). Carries the permanent,
  NSS-wide **Sangha Sevi ID** (`sangha_sevi_id`, format `SS1`, `SS2`, … — no zero-padding, per
  the project-wide loosened `id_sequence_master.padding_length` change), current membership
  type (Probationary/Regular/Associate/Honorary via `master_data` category
  `MEMBERSHIP_TYPE`), current status (via the unified `STATUS` category), and current Sakha
  (`organization_pk`). The Sangha Sevi ID never changes and is never reused, including across
  transfers.
- **`membership_status_history`** — append-only timeline of every status change
  (ACTIVE/SUSPENDED/LAPSED/…) with `effective_from`/`effective_to`. The *current* status still
  lives on `sangha_sevi`; this table exists purely so status history is never lost.
- **`membership_renewal_request`** — a request/approval workflow row (`PENDING` →
  `APPROVED`/`REJECTED`) created before a renewal is granted. A CHECK constraint
  (`chk_mem_renewal_req_review_consistency`) enforces that `PENDING` rows have no reviewer/date
  yet, and `APPROVED`/`REJECTED` rows always have a `reviewed_date`.
- **`membership_renewal_history`** — one row per *completed* renewal (financial-year validity,
  1 April–31 March). Distinct from the request table: a request is a workflow artifact that may
  be rejected; a history row is a permanent, never-deleted record that a renewal actually
  happened.
- **`membership_transfer_history`** — one row per Sakha-to-Sakha transfer
  (`old_organization_pk` → `new_organization_pk`, `chk_mem_transfer_different_orgs` guarantees
  they differ). Sangha Sevi ID is unchanged by a transfer; `old_local_sakha_erp_id`/
  `new_local_sakha_erp_id` are point-in-time snapshots for audit purposes only — the
  authoritative current/historical Local Sakha ERP IDs live on `membership_sakha_affiliation`.
- **`membership_sakha_affiliation`** — the **authoritative source of the Local Sakha ERP ID**
  (Tier 2 identity, e.g. `ESS1192`). One row per person per Sakha, never reassigned to a
  different person once issued. A partial unique index
  (`uq_mem_sakha_aff_active WHERE effective_to IS NULL`) enforces exactly one *active*
  affiliation per member at any time; on transfer, the old row is closed
  (`effective_to` set, `affiliation_status = 'ARCHIVED'`) and a new row is opened at the new
  Sakha with a new `local_sakha_erp_id` — the old row is archived, never deleted, and can be
  reactivated (`affiliation_status = 'REACTIVATED'`) if the member later returns to the same
  Sakha.
- **`membership_journey_event`** — a free-form, chronological timeline of lifecycle events
  (`MEMBERSHIP_CREATED`, `PROBATIONARY_STARTED`, `REGULAR_ENROLMENT`, `TRANSFER`,
  `STATUS_CHANGE`, `KUMARI_TRANSITION`, etc.). `event_type` is a plain `VARCHAR`, not an FK to
  `master_data` — the event catalogue is extensible and module-specific, controlled at the
  application layer rather than frozen as reference data.
- **`probationary_member_review`** — periodic/final/special review checkpoints for a
  Probationary member working toward Regular enrolment (Bye-Law §B(b): at least one year
  probationary + one year training). Records outcome (`PASS`/`FAIL`/`DEFERRED`), training
  completion, and the Sakha's recommendation — without overwriting or replacing the membership
  record itself.
- **`parichaya_patra`** — the annual Identity Card issued by Kendra Sangha. `document_number`
  is the **Kendra Number** (Tier 3 identity, format `<seq>/<FY start>/<FY end>`, e.g.
  `345/2026/2027`), globally unique (`uq_pp_document_number`). `affiliated_organization_pk` and
  `local_sakha_erp_id` are **point-in-time snapshots** of what was printed on that year's card —
  the live/authoritative affiliation still lives on `membership_sakha_affiliation`. A partial
  unique index (`uq_pp_active_per_member`) enforces at most one `ACTIVE` card per member.
- **`parichaya_patra_history`** — change log for a `parichaya_patra` row (`ISSUED`/`RENEWED`/
  `EXPIRED`/`CANCELLED`/`REPLACED`) with previous/new status. Historical records are never
  deleted.
- **`anumati_patra`** — the Probationary member's credential ("Admit Card," Bye-Law §B(a)),
  structurally similar to `parichaya_patra` (own `document_number`, validity range, status,
  partial unique "one ACTIVE per member" index) but with no Sakha-snapshot columns — it isn't
  tied to a specific Sakha the way the Identity Card is. Must be valid at least one year before
  Regular enrolment (Bye-Law §B(b)(i)). Numbering is **per issuing Sakha**: `issuing_organization_pk`
  records the minting Sakha and `document_number` is unique only within it
  (`uq_ap_document_number` = `UNIQUE(issuing_organization_pk, document_number)`). This replaced an
  earlier global `UNIQUE(document_number)` that collided (409) whenever two Sakhas each issued their
  first Anumati Patra of a financial year — both legitimately minting `1/<FY>/<FY>` from their own
  per-Sakha counters. (Parichaya Patra differs: its single Kendra-wide counter already yields
  globally-unique numbers, so `uq_pp_document_number` stays single-column.)
- **`anumati_patra_history`** — change log for an `anumati_patra` row, same shape and rationale
  as `parichaya_patra_history`.
- **`darshak_attendance_registration`** — (Tier 5) a member's
  registration to attend Sangha Puja as a Darshak at a **different** Sakha than their own
  (v1.1: `initiated_by_sangha_sevi_pk` records who raised it and `request_source` is `MEMBER_SELF` or `ADMIN_AUTOMATIC_ENTRY` — record-keeping only, never skips an approval step, DAR-009)
  (`chk_dar_att_reg_different_sakha` forbids `home_organization_pk = attending_organization_pk`).
  Goes through a 3-step approval chain (`PENDING_HOME_SAKHA` → `PENDING_PARICHALAK` →
  `PENDING_TARGET_SAKHA` → `APPROVED`/`REJECTED`/`REVOKED`); on `APPROVED`, the attending Sakha
  assigns a `darshak_local_number` (required by `chk_dar_att_reg_number_on_approval`, unique per
  attending org via `uq_dar_att_reg_local_number`, persistent per person per Sakha, never
  reassigned). Distinct from `membership_sakha_affiliation`, which tracks *home*-Sakha
  membership, not cross-Sakha attendance. A partial unique index
  (`uq_dar_att_reg_active`) enforces at most one `ACTIVE` `registration_status` row per member at
  a time.

- **`credential_sequence_counter`** — (Tier 5) backs
  `api/helpers.py::next_credential_document_number()`, which mints
  `parichaya_patra.document_number`/`anumati_patra.document_number` in `<seq>/<FY start>/<FY end>`
  format. One row per (`credential_type`, `scope_organization_pk`, `financial_year_start`) —
  `PARICHAYA_PATRA` is a single Kendra-wide counter, `ANUMATI_PATRA` is one counter per issuing
  Sakha — and the sequence restarts at 1 each 1 April (a new FY = a new row). Rows are created on
  demand by upsert, not seeded. Distinct from `id_sequence_master` (one flat, never-reset counter
  per business ID). `uq_credential_sequence_scope` makes the triple unique; the
  `credential_type` CHECK limits it to the two values above.
- **`14_sakha_only_membership_trigger.sql`** (no table) — enforces MBR-038A at the DB level: a
  member's `sangha_sevi.organization_pk` and `membership_sakha_affiliation.organization_pk` must
  reference a `SAKHA_SANGHA` organization (`trg_enforce_sakha_only_sangha_sevi`,
  `trg_enforce_sakha_only_affiliation`). The single exception is the reserved system account
  (`sangha_sevi.is_system_account = TRUE`, the seeded admin `SS1`), which may point at Kendra.

- **`sakha_local_number_counter`** — (Tier 6) backs `api/helpers.py::next_sakha_local_number()`,
  which auto-generates the bare numeric portion of a Tier 2 Local Sakha ERP Number
  (MBR-030C/MBR-048) when `insert_sakha_affiliation()` isn't given an explicit one. One row per
  (`organization_pk`, `namespace`) — `REGULAR` or `DARSHAK`, mirroring the two namespaces
  `compose_local_sakha_erp_id()` already composes. Unlike `credential_sequence_counter`, this
  counter carries **no financial-year column and never resets** — a Local Sakha ERP Number is
  permanent (MBR-030, MBR-022), not an annual credential number.
- **`membership_change_request`** — (Tier 6) the Sakha Transfer / Apply for Darshak workflow
  table (MBR-048, MBR-049): `PENDING_SOURCE_RELEASE` → `PENDING_DESTINATION_ACCEPT` →
  `COMPLETED`, with a rejection branch at either stage. `request_type` is `TRANSFER` or
  `DARSHAK` — on `COMPLETED`, a `TRANSFER` closes the old `membership_sakha_affiliation` row and
  opens a new one (plus a `membership_transfer_history` row); a `DARSHAK` opens a second,
  concurrently-active affiliation row at the destination Sakha without closing the home one. A
  partial unique index enforces at most one open (non-terminal-status) request per member at a
  time.

## The "Current State + History" Pairing Pattern

Membership is the first module to lean heavily on a recurring design idiom used throughout this
DDL: a **mutable "current state" table** paired with an **append-only history table** that
records every transition into or out of that state. This shows up three times:

1. `sangha_sevi.membership_status_master_data_pk` (current) ↔ `membership_status_history`
   (every change, with `effective_from`/`effective_to`).
2. `parichaya_patra` (current + past cards, since `status` distinguishes `ACTIVE` from
   `EXPIRED`/`CANCELLED`/`REPLACED`) ↔ `parichaya_patra_history` (the *events* that changed a
   given card's status — issuance, renewal, expiry, cancellation, replacement).
3. `anumati_patra` ↔ `anumati_patra_history` — identical shape to the Parichaya Patra pair.

The same idiom appears once more at a *relationship* granularity rather than a single-table
granularity: `membership_sakha_affiliation` is itself a "current + history" table for a
member's Sakha affiliation (no separate history table needed — old rows are simply closed via
`effective_to`, and `membership_transfer_history` records the *transfer events* between
affiliation periods). Two other tables — `membership_renewal_request` and
`membership_renewal_history` — split what could have been one table into a workflow table
(mutable until approved/rejected) and a permanent completed-renewal ledger, the same
history-never-overwritten principle applied to a process rather than a status field.

Why this pattern instead of just overwriting the current-state column: "History Never Deleted"
is a frozen project-wide principle (see `CLAUDE.md`); status/affiliation/document changes are
exactly the kind of business fact that must remain reconstructable for governance and
audit purposes (e.g. proving when a member transferred Sakhas, or when a Parichaya Patra was
replaced), not just what the *current* value happens to be.

## Non-Obvious Constraints

- **Three-tier identity split across three different tables.** Tier 1 (Sangha Sevi ID) lives on
  `sangha_sevi`; Tier 2 (Local Sakha ERP ID) lives on `membership_sakha_affiliation`, **not** on
  `sangha_sevi` — this was an explicit frozen decision (`MEM-PENDING-001 FROZEN`, referenced in
  `01_sangha_sevi.sql`'s own header comment) precisely because the Local Sakha ERP ID changes on
  transfer while the Sangha Sevi ID does not; Tier 3 (Kendra Number) lives on
  `parichaya_patra.document_number`.
- **`chk_mem_sakha_aff_status_consistency`** ties `effective_to` nullability to
  `affiliation_status`: open-ended rows (`effective_to IS NULL`) must be `ACTIVE` or
  `REACTIVATED`; closed rows (`effective_to IS NOT NULL`) must be `ARCHIVED`. This is enforced
  at the DB level, not just in application code.
- **`uq_mem_sakha_aff_local_id UNIQUE (organization_pk, local_sakha_erp_id)`** — a Local Sakha
  ERP ID is unique *within* a Sakha (not globally); the same numeric suffix can recur at a
  different Sakha (a member who transfers gets a new, Sakha-local ID at the new Sakha).
- **Three partial unique indexes enforcing "at most one active X per member"** —
  `uq_mem_sakha_aff_active` (one open affiliation), `uq_pp_active_per_member` (one active
  Parichaya Patra), `uq_ap_active_per_member` (one active Anumati Patra) — all implemented as
  `CREATE UNIQUE INDEX ... WHERE <condition>`, not table-level `CHECK` constraints, because the
  invariant spans multiple rows (a `CHECK` constraint can only see one row at a time).
- **Audit-actor FKs deferred to Pass 2.** Every `*_by_sangha_sevi_pk` column
  (`created_by_sangha_sevi_pk`, etc.) is a nullable `UUID` with no FK constraint in this pass —
  the same "Two-Pass DDL Strategy" gap noted for `role_master`/`permission_master` and
  Organization/Person, now finally resolvable in a later pass because `sangha_sevi` (the table
  those FKs would reference) exists as of this module. `01_sangha_sevi.sql`'s own header comment
  calls this out explicitly ("deferred to Pass 2 for initial bootstrap — first member
  creation").
- **`event_type` on `membership_journey_event` is a plain `VARCHAR`, not an FK** — deliberately
  not constrained to `master_data`, since the event catalogue is extensible at the application
  layer (unlike, say, membership type or status, which are frozen reference data).
- **No zero-padding on any business identifier in this module** — `sangha_sevi_id` (`SS1`),
  `local_sakha_erp_id` (`ESS1192`), and Kendra/Anumati document numbers all follow the
  project-wide loosened ID-format decision (`id_sequence_master`'s `padding_length` CHECK now
  allows `0`), documented in `docs/00_Project_Governance/STD/01_project_standards.md` and
  `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md`.

See `docs/03_Solution/modules/membership/05_membership_table_design.md` (`SOL-MEM-005`) for the
full design rationale — noting the design-doc status caveat at the top of this file. See also
`docs/03_Solution/modules/membership/06_darshak_attendance_registration.md` (Tier 5)
for the `darshak_attendance_registration` design rationale,
`docs/PROJECT_DOCUMENTATION.md` for the tier-by-tier plan, and
`docs/03_Solution/api/API_CONTRACT.md` §8 for how these tables are exposed over HTTP (note: no
router reads or writes `darshak_attendance_registration` — it exists in DDL only as of this
pass. `darshak_local_number` in `api/routers/admin.py`'s user queries comes from
`membership_sakha_affiliation` (alias `dmsa`), not from this table, and the dashboard's
attendance % is reported as "not tracked" because this is a registration/approval record, not
an attendance log).
