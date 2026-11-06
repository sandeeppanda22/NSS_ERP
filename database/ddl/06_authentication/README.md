# database/ddl/06_authentication/

Authentication & Security Module DDL — 5 tables. **Implemented (released in v0.11.0)** (see `docs/PROJECT_DOCUMENTATION.md` → Tier 5).

Authority: SOL-AUTH-001, SOL-AUTH-002, SOL-AUTH-004, SOL-AUTH-005, SOL-AUTH-006, SOL-AUTH-007,
Tier 5 decisions (2026-09-15), Tier 5.1 self-service reset (2026-09-20).

## DDL Execution Order

Execute AFTER Person DDL (`database/ddl/03_person/`) and Organization DDL
(`database/ddl/02_organization/`) — `user_account` FKs to `person`; `registration_claim` FKs to
`person`, `organization`, and Foundation's `master_data`.

| # | File | Table | Depth | Depends on |
|--:|------|-------|------:|------------|
| 01 | `01_user_account.sql` | `user_account` | 3 | `person` |
| 02 | `02_password_history.sql` | `password_history` | 4 | `user_account` |
| 03 | `03_registration_claim.sql` | `registration_claim` | 3 | `user_account`, `person`, `organization`, `master_data` |
| 04 | `04_password_reset_token.sql` | `password_reset_token` | 4 | `user_account` |
| 05 | `05_user_session.sql` | `user_session` | 4 | `user_account` |
| 06 | `06_registration_claim_legacy_member_patch.sql` | *(idempotent patch)* | — | `registration_claim`; adds the GDR-009 `is_legacy_member`/`darshak_is_legacy_member` columns and CHECKs to existing databases |

Run as Phase 10 in `database/scripts/02_build.sh`/`.ps1`, after Phase 9 (grant
`nss_db_backend`) and before Phase 12 (grant `nss_db_writer`, which must follow so its
`ALL TABLES` grant covers these tables). The Depth column above is the per-module numbering; each
SQL file's own `-- Depth:` header comment records one less for every table here (`user_account` 2,
the other four 3) — cosmetic only. There is no seed folder for this module — the only auth data
ever seeded is the admin account from `database/seed/04_admin/` (Phase 13).

## What These Tables Are For

- **`user_account`** — one row per `person` (`UNIQUE (person_pk)`) carrying the Argon2
  `password_hash`, `account_status` (`ACTIVE`/`LOCKED`/`INACTIVE`/`PENDING_APPROVAL`),
  `force_password_change`, password-expiry (`password_changed_at`/`password_expires_at`,
  365-day default), and lockout tracking (`failed_login_attempts`, `locked_until`,
  `last_failed_login_at`). There is **no `login_id`/`username` column** — the login identifier
  (Sangha Sevi ID, falling back to Person ID) is resolved at authentication time via the
  `person_pk` FK, not stored on this table (`api/routers/auth.py::login()`).
- **`password_history`** — append-only log of every past `password_hash` for a user, with a
  `changed_reason` (`USER_CHANGE`/`ADMIN_RESET`/`SELF_RESET`/`EXPIRY`/`INITIAL`). Never the
  current credential (that lives on `user_account` itself, AUTH-BR-015) — only used for reuse
  prevention (current API only checks against the *current* hash, not the full history, despite
  this table existing).
- **`registration_claim`** — self-declared membership intent captured at self-registration
  (`POST /api/v1/register`), pending Sakha-admin review: claimed organization, membership type,
  Local Sakha Number (`claimed_local_sakha_number`, not checked against `sangha_sevi` at registration; present iff the explicit `is_legacy_member` flag is set — GDR-009, with `darshak_is_legacy_member` for the attendance Sakha; patch `06_registration_claim_legacy_member_patch.sql` carries the columns/CHECKs to existing DBs), and
  optional Darshak-attendance organization (Regular/Associate only — GDR-009 §2B). The claimed Patra number `claimed_credential_document_number` is non-NULL only for a legacy member (same flag, GDR-009 §2A; application-enforced, no DDL change). Lifecycle `PENDING → APPROVED | REJECTED`; a partial
  unique index enforces at most one `PENDING` claim per `user_account`. Approval (`api/routers/
  claim_approval.py`) is what actually creates the `sangha_sevi`/`membership_sakha_affiliation`
  rows — this table itself never does.
- **`password_reset_token`** — time-limited (15 min), single-use, Argon2-hashed 6-digit OTPs for
  the "Forgot Password" self-service flow (Tier 5.1). Rate-limited at the API layer (3/hour),
  not by a DB constraint.
- **`user_session`** — stateful session/device record created at login (Tier 5 advisory A4
  resolution, 2026-10-05): `issued_at` (login time), `last_seen_at` (bumped on each access-token
  refresh), `expires_at` (mirrors the refresh token's exp), `revoked_at` (set on logout/explicit
  "sign out this device"), plus `user_agent`/`ip_address`/`device_label` captured at login for
  display in a "logged-in devices" UI. A partial index on `(user_account_pk, revoked_at) WHERE
  revoked_at IS NULL` backs the active-sessions-list query. No soft-delete columns — unlike every
  other table in this pass, sessions are transient, not business records, so their lifecycle is
  expressed entirely through `revoked_at` (and `expires_at`), making a separate `is_active`/
  `deleted_at` pair redundant.

## Key FK Relationships

- `user_account.person_pk` → `nss.person(person_pk)`, `UNIQUE` — one account per person.
- `password_history.user_account_pk` → `user_account(user_account_pk)`.
- `registration_claim.user_account_pk` → `user_account`; `.person_pk` → `nss.person` (denormalized
  for query convenience); `.claimed_organization_pk`/`.darshak_organization_pk` →
  `nss.organization` (two separate FKs to the same table); `.claimed_membership_type_master_data_pk`
  → `nss.master_data`; `.reviewed_by_user_account_pk` → `user_account` (a second FK to the same
  table, for the reviewing admin).
- `password_reset_token.user_account_pk` → `user_account`.
- `user_session.user_account_pk` → `user_account`.

Like every other module, audit-actor columns (`created_by_sangha_sevi_pk`, etc.) are plain
nullable UUIDs in the table DDL; their FKs against `sangha_sevi` are added by the single
catalog-driven patch `database/ddl/13_audit_actor_fk/01_audit_actor_fk_patch.sql` (build Phase 13c).

## Non-Obvious Constraints

- **`uq_user_account_person`** — `UNIQUE (person_pk)`: one `user_account` per person, enforced at
  the DB level, not just the API.
- **`chk_user_account_status`** — `CHECK (account_status IN ('ACTIVE', 'LOCKED', 'INACTIVE',
  'PENDING_APPROVAL'))`. Note the API layer never actually sets `LOCKED` as a stored status —
  lockout is tracked via `failed_login_attempts`/`locked_until` instead, and self-clears after
  30 seconds; `LOCKED` in this CHECK is unused by any router as of this pass.
- **`uq_registration_claim_one_pending`** — a partial unique index, `UNIQUE (user_account_pk)
  WHERE claim_status = 'PENDING'` (AUTH-BR-083) — the DB-level guarantee that a user can't stack
  multiple pending claims.
- **`idx_password_reset_token_user_active`** — a plain (non-unique, non-partial) composite index
  on `(user_account_pk, is_used, expires_at)`, used by the "find my active OTP" lookup in
  `api/routers/auth.py`.

See `docs/03_Solution/modules/authentication/06_registration_claim_business_rules.md` and
`07_registration_claim_table_design.md` for the `registration_claim` design rationale. See
`docs/PROJECT_DOCUMENTATION.md` → Architecture ("Tier 5") and Key Workflow #9 for the full
authentication/registration/approval flow this DDL supports.
