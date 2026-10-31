# database/ddl/01_foundation/

Foundation Module DDL — 15 tables (Depths 0–3), plus one cross-cutting audit trigger. Includes
`festival_master`/`festival_calendar_date` (Festival Calendar feature;
full table design in `docs/03_Solution/architecture/FESTIVAL_CALENDAR_ARCHITECTURE.md`).
`post_office` was added and retired on 2026-10-02 (Simplified Geography Model), then
**reinstated on 2026-10-03** (`13_post_office.sql`, Member-Assisted Geographic Entry amendment)
as a child of `postal_code` — one PIN can carry many post offices. `district`, `postal_code`,
`post_office` and `city_village` are the four **member-writable** geographic levels and share the
member-assisted-entry columns described under "Member-Assisted Geographic Entry" below.
`14_system_event_log.sql`/`15_audit_trigger.sql` were added in Tier 5 (v0.11.0).

Authority: SOL-ARCH-010 (DDL Creation Order) + Amendment (PIN Code Geographic
Model), SOL-FND-004 (Foundation Table Design); `system_event_log`/the audit trigger cite
SOL-AUDIT-004 §8–9 (Data Change Architecture, 2026-09-22).

## File Execution Order

Execute files in numeric order. Each file depends only on tables created
by earlier-numbered files in this directory.

> **Note:** Extensions (`pgcrypto`, `pg_trgm`, `btree_gin`) have moved to
> `database/scripts/01_extensions.sql` — run as a prerequisite before DDL.

| # | File | Table | Depth | Global Seq |
|--:|------|-------|------:|-----------:|
| 02 | `02_master_category.sql` | `master_category` | 0 | #1 |
| 03 | `03_system_setting.sql` | `system_setting` | 0 | #2 |
| 04 | `04_id_sequence_master.sql` | `id_sequence_master` | 0 | #3 |
| 05 | `05_country.sql` | `country` | 0 | #4 |
| 06 | `06_document_master.sql` | `document_master` | 0 | #5 |
| 07 | `07_field_change_log.sql` | `field_change_log` | 0 | #6 |
| 08 | `08_master_data.sql` | `master_data` | 1 | #18 |
| 09 | `09_state.sql` | `state` | 1 | #19 |
| 10 | `10_district.sql` | `district` | 2 | #26 |
| 11 | `11_city_village.sql` | `city_village` | 3 | #32 |
| 12 | `12_postal_code.sql` | `postal_code` | 1 | #87 (amendment) |
| 13 | `13_post_office.sql` | `post_office` | 2 | — (Member-Assisted Geographic Entry) |
| 14 | `14_system_event_log.sql` | `system_event_log` | 0 | — (Tier 5) |
| 15 | `15_audit_trigger.sql` | *(no table — trigger function + `DO` block attaching it to every `nss.*` table)* | — | — (Tier 5) |
| 16 | `16_festival_master.sql` | `festival_master` | 0 | — (Festival Calendar) |
| 17 | `17_festival_calendar_date.sql` | `festival_calendar_date` | 1 | — (Festival Calendar) |

**Note:** File 12 depends only on `state` (Depth 1 — `postal_code` has a direct
`state_pk` FK). It is
numbered after the original 11 files for clarity but
executes correctly in sequence because its dependency is already created
by earlier files. **Files 14–15 (Tier 5) must run last** — `15_audit_trigger.sql`
attaches `nss.fn_audit_trigger()` to every table already present in the `nss` schema at the
time it runs (`SELECT tablename FROM pg_tables WHERE schemaname = 'nss'`), excluding only
`system_event_log` and `field_change_log` themselves; if it ran before later modules'
DDL (Organization/Person/Family/Membership/Authentication/Administration), those tables
would silently end up without an audit trigger. `02_build.sh`/`02_build.ps1` run it as the
final step of the full build, after every other module's DDL.

## Execution Command

```bash
# As nss_db_owner against the nss_erp database (files 14/15 are excluded here — they
# must run last in the whole build, see the Note above):
for f in database/ddl/01_foundation/0*.sql database/ddl/01_foundation/1[0-3]*.sql \
         database/ddl/01_foundation/1[67]*.sql; do
    psql -U nss_db_owner -d nss_erp -f "$f"
done
```

---

## Table Descriptions

### 1. `master_category` (Depth 0, #1 of 87)

The top-level classification registry. Every domain-specific lookup value in the
ERP (gender, membership type, relationship type, etc.) belongs to a category
defined here. This replaces the earlier per-domain master table pattern (e.g.
separate `gender_master`, `membership_type_master`) with a single two-table
design: `master_category` + `master_data`.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `master_category_pk` | UUID | PK, auto | Internal primary key |
| `category_code` | VARCHAR(50) | UNIQUE, NOT NULL | Machine-readable code (e.g. `GENDER`, `MEMBERSHIP_TYPE`) |
| `category_name` | VARCHAR(100) | UNIQUE, NOT NULL | Human-readable name (e.g. "Gender", "Membership Type") |
| `description` | TEXT | NULL | Optional description of the category |
| `display_order` | INTEGER | NOT NULL, default 0 | UI presentation ordering |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `category_code`, `is_active`

---

### 2. `system_setting` (Depth 0, #2 of 87)

Key-value store for application-wide configuration. Each setting has a typed
value (`STRING`, `INTEGER`, `BOOLEAN`, `DATE`, `JSON`) so the application layer
can validate and cast correctly. Used for runtime-configurable parameters that
don't warrant a code deployment to change.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `system_setting_pk` | UUID | PK, auto | Internal primary key |
| `setting_key` | VARCHAR(100) | UNIQUE, NOT NULL | Setting identifier (e.g. `DEFAULT_COUNTRY`) |
| `setting_value` | TEXT | NOT NULL | Setting value (stored as text, interpreted per `data_type`) |
| `description` | TEXT | NULL | What this setting controls |
| `data_type` | VARCHAR(20) | NOT NULL, default `STRING` | CHECK: `STRING`, `INTEGER`, `BOOLEAN`, `DATE`, `JSON` |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `setting_key`, `is_active`

---

### 3. `id_sequence_master` (Depth 0, #3 of 87)

Configuration registry for generating human-readable business IDs. Each row
defines a sequence with a prefix, a counter, and a `padding_length`. The
application layer reads `current_value`, increments it, and formats the ID as
`{prefix}{current_value, zero-padded to padding_length}` (e.g. `SKH00000001`
for the first Sakha, since the seeded `SAKHA` sequence has `padding_length =
8`). The `chk_id_sequence_padding` CHECK constraint allows `padding_length`
between 0 and 12 (loosened from 2–12) so a future sequence can opt into
unpadded IDs (`{prefix}{current_value}`, e.g. `SKH1`), but no currently
seeded sequence has `padding_length = 0` yet — see
`database/seed/01_foundation/README.md` for the actual per-sequence values.

Unique organizations (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, and the singleton ADVISORY_BOARD) do not use
sequences — they receive fixed codes directly from seed data.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `id_sequence_master_pk` | UUID | PK, auto | Internal primary key |
| `sequence_code` | VARCHAR(50) | UNIQUE, NOT NULL | Sequence identifier (e.g. `PERSON`, `SAKHA`) |
| `sequence_name` | VARCHAR(100) | UNIQUE, NOT NULL | Human-readable name |
| `prefix` | VARCHAR(20) | NOT NULL | ID prefix (e.g. `P`, `SKH`, `ANC`) |
| `current_value` | BIGINT | NOT NULL, default 0 | Last used counter value; CHECK >= 0 |
| `padding_length` | INTEGER | NOT NULL, default 8 | Zero-padding width; CHECK 0–12 (loosened from 4–12 to allow unpadded business IDs like `P1`, `SS1` — see `docs/00_Project_Governance/STD/01_project_standards.md`) |
| `description` | TEXT | NULL | Optional description |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `sequence_code`, `is_active`

---

### 4. `country` (Depth 0, #4 of 87)

Root of the geographic reference hierarchy. Stores ISO 3166-1 alpha-2 country
codes. Every downstream geographic entity (state, district, city_village,
postal_code) traces back to a country.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `country_pk` | UUID | PK, auto | Internal primary key |
| `country_code` | CHAR(2) | UNIQUE, NOT NULL | ISO 3166-1 alpha-2 code (e.g. `IN`, `US`) |
| `country_name` | VARCHAR(100) | UNIQUE, NOT NULL | Full country name |
| `display_order` | INTEGER | NOT NULL, default 0 | UI presentation ordering (India first) |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `country_code`, `is_active`

---

### 5. `document_master` (Depth 0, #5 of 87)

Central document storage registry. Every uploaded file in the ERP (photos,
ID proofs, certificates, property documents, meeting minutes) is catalogued
here. Owned by Foundation (DOC-ARCH-001); logical design originates from
Person module (§54).

Person-specific FKs (`person_pk`, `uploaded_by_sangha_sevi_pk`) are NOT
included in this DDL — they are deferred to Pass 2 ALTER TABLE after those
tables exist.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `document_master_pk` | UUID | PK, auto | Internal primary key |
| `document_type_code` | VARCHAR(50) | NOT NULL | Document classification (matches `master_data` DOCUMENT_TYPE values) |
| `document_number` | VARCHAR(100) | NULL | External document number (e.g. Aadhaar number, PAN) |
| `document_name` | VARCHAR(255) | NOT NULL | Original file name or descriptive title |
| `storage_path` | TEXT | NOT NULL | File system or object storage path |
| `file_size_bytes` | BIGINT | NULL | File size in bytes |
| `mime_type` | VARCHAR(100) | NULL | MIME type (e.g. `application/pdf`, `image/jpeg`) |
| `version` | INTEGER | NOT NULL, default 1 | Document version; CHECK >= 1 |
| `checksum` | VARCHAR(128) | NULL | File integrity hash |
| `description` | TEXT | NULL | Optional description |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL, auto | When the file was uploaded |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `document_type_code`, `is_active`, `document_number` (partial,
WHERE NOT NULL)

---

### 6. `field_change_log` (Depth 0, #6 of 87)

Field-level change log — the "what changed" half of the audit trail, read by
`GET /api/v1/audit/change-log`. Populated **automatically** by
`nss.fn_audit_trigger()` (see `15_audit_trigger.sql`), one row per field, for
every `INSERT`/`UPDATE`/`DELETE` on every audited `nss` table. Per
AUDIT-ARCH-001 coverage is complete and defined by exclusion:

* `created_at` / `updated_at` columns are skipped (change on every write;
  `changed_at` already records "when");
* `id_sequence_master` and `credential_sequence_counter` are skipped entirely
  (counter rows mutate on every ID mint — `current_value: 41 → 42` is
  mechanical noise). They still get row-level rows in `system_event_log`.

No application code writes here; `nss_db_backend` holds SELECT only. Rows are
INSERT-only — there is no UPDATE/DELETE path.

Per-operation shape:

| `action` | `old_value` | `new_value` | Rows written |
|----------|-------------|-------------|--------------|
| `CREATE` | NULL | the value set | one per populated field |
| `UPDATE` | previous value | new value | one per **changed** field |
| `DELETE` | the value lost | NULL | one per populated field |

`action` is stored explicitly rather than inferred, because an `UPDATE` that
sets a field from NULL to a value is otherwise indistinguishable from a
`CREATE`.

No FK constraints — `table_name` and `record_pk` are stored as plain values
(VARCHAR + UUID) to avoid circular dependencies. Both actor columns are
likewise raw UUIDs without FK constraint. Referential integrity is
enforced by the application layer.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `field_change_log_pk` | UUID | PK, auto | Internal primary key |
| `action` | VARCHAR(20) | NULL, CHECK in (CREATE, UPDATE, DELETE) | Which DB operation produced this row |
| `table_name` | VARCHAR(100) | NOT NULL | Name of the table that was changed |
| `record_pk` | UUID | NOT NULL | PK of the changed record |
| `field_name` | VARCHAR(100) | NOT NULL | Column name that changed |
| `old_value` | TEXT | NULL | Previous value (NULL for new records) |
| `new_value` | TEXT | NULL | New value (NULL for deletions) |
| `change_reason` | TEXT | NULL | Why the change was made |
| `changed_at` | TIMESTAMPTZ | NOT NULL, auto | When the change occurred |
| `changed_by_sangha_sevi_pk` | UUID | NULL | Who made the change (no FK — application-enforced) |
| `changed_by_user_account_pk` | UUID | NULL | Acting account — recorded because an authenticated user does not always have a Sangha Sevi record |

Both actor columns are NULL for public self-registration and for seed/system
operations.

**Indexes:** `(table_name, record_pk)`, `changed_at`, `(table_name, field_name)`,
`(changed_by_sangha_sevi_pk, changed_at)`, `action`

---

### 7. `master_data` (Depth 1, #18 of 87)

The value-level lookup table. Each row is a specific value belonging to a
`master_category`. For example, category `GENDER` contains values `MALE`,
`FEMALE`, `OTHER`. This is the child half of the two-table master data pattern.

Other modules reference `master_data` via FK to classify entities (e.g.
`person.gender_master_data_pk` → `master_data.master_data_pk` where the
category is `GENDER`).

**FK:** `master_category_pk` → `master_category`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `master_data_pk` | UUID | PK, auto | Internal primary key |
| `master_category_pk` | UUID | FK, NOT NULL | Parent category |
| `value_code` | VARCHAR(50) | NOT NULL | Machine-readable code within category |
| `value_name` | VARCHAR(150) | NOT NULL | Human-readable display name |
| `description` | TEXT | NULL | Optional description |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering within category |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Unique:** `(master_category_pk, value_code)` — no duplicate codes within a category

**Indexes:** `master_category_pk`, `is_active`, `value_code`,
`value_name` (GIN trigram for fuzzy search)

---

### 8. `state` (Depth 1, #19 of 87)

Second level of the geographic hierarchy. Stores states, provinces, union
territories, or equivalent administrative divisions within a country.

**FK:** `country_pk` → `country`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `state_pk` | UUID | PK, auto | Internal primary key |
| `country_pk` | UUID | FK, NOT NULL | Parent country |
| `state_code` | VARCHAR(20) | NOT NULL | State/province code (e.g. `OD` for Odisha) |
| `state_name` | VARCHAR(100) | NOT NULL | Full state name |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering within country |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Unique:** `(country_pk, state_code)`, `(country_pk, state_name)`

**Indexes:** `country_pk`, `is_active`, `state_name` (GIN trigram)

---

### 9. `district` (Depth 2, #26 of 87)

Third level of the geographic hierarchy. Stores districts within a state.
Seeded with all 785 Indian districts (numeric LGD `district_code`); non-India districts populated at
runtime.

**FK:** `state_pk` → `state`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `district_pk` | UUID | PK, auto | Internal primary key |
| `state_pk` | UUID | FK, NOT NULL | Parent state |
| `district_code` | VARCHAR(20) | NOT NULL | District code (e.g. `KHR` for Khordha) |
| `district_name` | VARCHAR(100) | NOT NULL | Full district name |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering within state |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Member-assisted columns** (see section below) are also present: `entry_status`, `submitted_by_sangha_sevi_pk`, `reviewed_by_sangha_sevi_pk`, `reviewed_at`, `admin_remarks`, `corrected_into_district_pk`.

**Unique (partial, `entry_status = 'APPROVED' AND is_active`):** `uq_district_state_code_approved (state_pk, district_code)`, `uq_district_state_name_approved (state_pk, district_name)`

**Indexes:** `state_pk`, `is_active`, `entry_status`, `district_name` (GIN trigram)

---

### 10. `city_village` (Depth 3, #32 of 87)

Fourth level of the geographic hierarchy. Stores individual localities
(cities, towns, villages) within a district. Seeded all-India from the
Simplified Geography Model (2026-10-02): village rows resolve `district_pk`
directly from the government village-directory's numeric district code;
a small number of urban-only localities (pins with no village row) resolve
`district_pk` via local-body name matching and may be left NULL when the
match is ambiguous. `district_pk` is nullable for this reason — an
unresolved district should not block a locality from loading. A direct
nullable `postal_code_pk` FK is the primary location anchor
(city_village → PIN → state).

**FKs:** `district_pk` → `district` (nullable), `postal_code_pk` → `postal_code` (nullable)

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `city_village_pk` | UUID | PK, auto | Internal primary key |
| `district_pk` | UUID | FK, NULL | Parent district (NULL if unresolved) |
| `postal_code_pk` | UUID | FK, NULL | PIN this locality belongs to |
| `city_village_code` | VARCHAR(20) | NOT NULL | Locality code |
| `city_village_name` | VARCHAR(150) | NOT NULL | Full locality name |
| `city_village_type` | VARCHAR(20) | NOT NULL | CHECK: `CITY`, `TOWN`, `VILLAGE` |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering within district |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Member-assisted columns** (see section below) are also present, with `corrected_into_city_village_pk`.

**Unique (partial, `entry_status = 'APPROVED' AND is_active`):** `(district_pk, city_village_code)`, `(district_pk, city_village_name)`,
`(postal_code_pk, city_village_name)`

**Indexes:** `district_pk`, `postal_code_pk`, `is_active`, `entry_status`, `city_village_name` (GIN trigram)

---

### 11. `postal_code` (Depth 1, #87 of 87 — amendment, v2.0 2026-10-02)

PIN code / postal code reference table. State-scoped with a direct `state_pk`
FK for administrative ownership (PIN → State is always deterministic — the dominant
state is chosen for the handful of PINs that legitimately span state lines).
`city_village` carries a direct `postal_code_pk` FK (one city/village → one PIN);
PIN → District is NOT 1:1 (many PINs legitimately span 2+ districts), so district is
intentionally NOT a column here — it is reached through `city_village`, which carries
its own `district_pk` per locality row. Supports address validation, autocomplete, and
map-based search ("find nearby Sanghas"). As of the Simplified Geography Model amendment
(2026-10-02), this table no longer carries `country_pk` (redundant — reachable via
`state_pk → state.country_pk`) or `post_office_name` (no source once `post_office` was
retired; the new 4-file government source carries no post-office data, only
village/urban locality names, which now live on `city_village`).

**FK:** `state_pk` → `state`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `postal_code_pk` | UUID | PK, auto | Internal primary key |
| `state_pk` | UUID | FK, NOT NULL | State this PIN code belongs to |
| `postal_code` | VARCHAR(20) | NOT NULL | The PIN / postal code value (e.g. `751024`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Member-assisted columns** (see section below) are also present, with `corrected_into_postal_code_pk`.

**Unique (partial, `entry_status = 'APPROVED' AND is_active`):** `uq_postal_code_code_approved (postal_code)` — one approved row per PIN

**Indexes:** `state_pk`, `postal_code`, `is_active`, `entry_status`

---

### 13. `post_office` (Depth 2, Member-Assisted Geographic Entry — 2026-10-03)

Post offices under a PIN (one HO plus several SO/BO per `postal_code`). Fourth member-writable
geographic level. Seeded in bulk by `seed/01_foundation/08c_post_office_bulk.sql`.

**FK:** `postal_code_pk` → `postal_code`; `corrected_into_post_office_pk` → `post_office` (self).

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `post_office_pk` | UUID | PK, auto | Internal primary key |
| `postal_code_pk` | UUID | FK, NOT NULL | Parent PIN |
| `post_office_name` | VARCHAR(150) | NOT NULL | Post office name |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering |
| member-assisted columns | — | — | `entry_status`, `submitted_by_sangha_sevi_pk`, `reviewed_by_sangha_sevi_pk`, `reviewed_at`, `admin_remarks`, `corrected_into_post_office_pk` |
| audit columns | — | — | `created_at`, `updated_at`, `deleted_at`, `is_active` |

**Unique (partial, APPROVED + active):** `uq_post_office_pin_name_approved (postal_code_pk, post_office_name)`

**Indexes:** `postal_code_pk`, `is_active`, `entry_status`, `post_office_name` (GIN trigram)

---

### `festival_master` / `festival_calendar_date` (Depths 0 / 1, Festival Calendar)

`16_festival_master.sql` — festival registry (`festival_code` and `festival_name` each unique,
`festival_name_odia`, `lunar_basis`, `is_erp_reference_date` flagging the festival the ERP uses as a
reference date, `display_order`, standard `is_active`/`deleted_at` soft-delete with
`chk_festival_master_soft_delete`). `17_festival_calendar_date.sql` — one entered (never computed)
observed date per festival per year: `UNIQUE (festival_master_pk, calendar_year)`, `observed_date`
must fall in `calendar_year` (`chk_festival_calendar_date_year_matches`), `is_confirmed`,
`source_reference`, `remarks`. Seeded by `seed/01_foundation/10_festival_calendar.sql`; edited via
`FOUNDATION_CALENDAR_MANAGE` (NSS_ERP_ADMIN only). Design: `docs/03_Solution/architecture/FESTIVAL_CALENDAR_ARCHITECTURE.md`.
These are built in Phase 1 (despite file numbers 16/17) so the Phase 14 audit trigger attaches to them.

---

### Member-Assisted Geographic Entry (`district`, `postal_code`, `post_office`, `city_village`)

A member may type a geographic value not yet in the lists; it is inserted as
`entry_status = 'PENDING'` (quarantined from shared dropdowns) via the
`POST /api/v1/foundation/{districts|postal-codes|post-offices|city-villages}/propose` endpoints, and a
`FOUNDATION_MANAGE` admin approves it (`APPROVED`) or corrects it (`CORRECTED`, with
`corrected_into_<entity>_pk` pointing at the canonical survivor — enforced by
`chk_<table>_correction`). Seeded rows start `APPROVED`. Uniqueness is enforced only among
`APPROVED` active rows (partial unique indexes, FND-BR-090) so a PENDING submission never collides
with a canonical row. `submitted_by_`/`reviewed_by_sangha_sevi_pk` are created as plain nullable
UUIDs here (Foundation builds before Membership) and get real FKs from
`05_membership/16_foundation_audit_fk.sql` (Phase 7b of `02_build.sh`). Authority: SOL-FND-004
§16.7–16.8, FND-BR-085..090. Review API: `api/routers/geo_approval.py`.

---

### 12. `system_event_log` (Depth 0, Tier 5)

Centralized, immutable audit trail (SOL-AUDIT-004 §8–9). Every authenticated write
operation is expected to append a row here — either explicitly via the application-layer
`api/helpers.py::log_audit()` helper (called from the auth, admin, family, foundation, claim-approval,
geo-approval and registration routers), or automatically via the `nss.fn_audit_trigger()` database trigger
(`15_audit_trigger.sql`, below) attached to every other `nss.*` table. Rows are INSERT-only
— no UPDATE/DELETE path exists in the application or DDL.

No FK constraints — `record_pk`/`actor_sangha_sevi_pk`/`actor_user_account_pk` are stored as
plain UUID values (same pattern as `field_change_log`) to avoid circular dependencies, since
this table must be creatable at Depth 0 yet needs to reference rows in every other table.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `system_event_log_pk` | UUID | PK, auto | Internal primary key |
| `event_at` | TIMESTAMPTZ | NOT NULL, auto | When the event occurred |
| `actor_sangha_sevi_pk` | UUID | NULL, no FK | Who performed the action (NULL = system/unauthenticated) |
| `actor_user_account_pk` | UUID | NULL, no FK | User account cross-reference (e.g. for pre-`sangha_sevi` login events) |
| `action` | VARCHAR(50) | NOT NULL | `CREATE`/`UPDATE`/`DELETE`/`APPROVE`/`REJECT`/`STATUS_CHANGE`/`LOGIN`/`PASSWORD_CHANGE`/etc. |
| `table_name` | VARCHAR(100) | NOT NULL | Table the event happened on |
| `record_pk` | UUID | NOT NULL, no FK | PK of the affected record |
| `module` | VARCHAR(50) | NULL | Functional area, e.g. `admin`/`auth`/`family`/`registration`/`trigger` (the DB-trigger path always sets `'trigger'`) |
| `summary` | VARCHAR(500) | NULL | Human-readable one-line summary |
| `detail` | JSONB | NULL | Structured payload — app-layer calls pass a free-form summary string; the DB trigger passes `{"new": ...}`/`{"old": ...}`/`{"changed": {...}}` |
| `is_success` | BOOLEAN | NULL, default TRUE | TRUE = success, FALSE = failure, NULL = not applicable |

**Indexes:** `(table_name, record_pk)`, `actor_sangha_sevi_pk` (partial, `WHERE NOT NULL`),
`event_at`, `(module, event_at)`, `(action, event_at)`

**Note — two independent write paths, not yet reconciled:** the application-layer
`log_audit()` calls (e.g. in `family.py`) and the database-level `fn_audit_trigger()` (below) can
both fire for the *same* write (e.g. `INSERT INTO nss.family_group` triggers both the trigger
*and* an explicit `log_audit()` call in `create_family()`), producing two rows per event with
different `module`/`summary`/`detail` shapes rather than one. No de-duplication exists yet.

---

### `15_audit_trigger.sql` — `nss.fn_audit_trigger()` (no new table)

Not a table file — a `SECURITY DEFINER` PL/pgSQL trigger function plus a `DO $$ ... $$` block
that dynamically attaches an `AFTER INSERT OR UPDATE OR DELETE` trigger
(`trg_audit_<table>`) to every table currently in the `nss` schema (via
`pg_tables`), excluding `system_event_log` and `field_change_log` themselves.

It writes **two** logs per operation:

1. **`system_event_log`** — one row-level event. On `UPDATE` it diffs `OLD`/`NEW` via
   `jsonb_each` and stores only the changed columns; on `INSERT`/`DELETE` it stores the
   full new/old row as JSONB.
2. **`field_change_log`** — field-level detail, one row per field, for all three
   operations (`action` = CREATE/UPDATE/DELETE). Per AUDIT-ARCH-001 this is complete and
   exclusion-defined: the `created_at`/`updated_at` columns are skipped everywhere, and
   the counter tables `id_sequence_master` / `credential_sequence_counter` are skipped
   wholesale (their `current_value` mutates on every ID mint). Excluded tables still get
   their `system_event_log` row, so schema coverage stays complete.

Actor identity comes from two Postgres session variables —
`nss.actor_sangha_sevi_pk` / `nss.actor_user_account_pk` — and both are stamped onto every
row written to either log; if unset, actor columns are simply `NULL`.
`api/dependencies/auth.py`'s `get_write_connection()` sets them via
`SELECT set_config('nss.actor_...', %s, TRUE)` after resolving the caller from the JWT
(the `TRUE` third argument scopes it to the current transaction).

**They must be set on the connection the write runs on.** Setting them on the read-pool
connection leaves the trigger blind, because writes — and therefore the trigger — execute on
the separate `nss_db_writer` pool. Idempotent — re-running `DROP TRIGGER IF EXISTS` +
`CREATE TRIGGER` for every table on each build.

Because it dynamically discovers `nss` tables at *run time* rather than listing them, this
file must execute **after every other module's DDL** (see the Note on Files 14–15 above) or
tables created later would never get a trigger attached — there is no re-run mechanism if a
new table is added after the initial build.

---

## Design Decisions

- **No audit-actor FKs** — `created_by_sangha_sevi_pk` / `updated_by_sangha_sevi_pk` /
  `deleted_by_sangha_sevi_pk` are NOT included in Foundation tables. They will be added
  via ALTER TABLE in Pass 2 after `sangha_sevi` exists (SOL-ARCH-010 §5).
- **Soft-delete backfill** — `deleted_at TIMESTAMPTZ NULL` plus a
  `(is_active = TRUE AND deleted_at IS NULL) OR (is_active = FALSE AND deleted_at IS NOT NULL)`
  CHECK constraint added to the original 10 tables that carry `is_active` (the later `post_office`, `festival_*` tables carry the same CHECK)
  (`master_category`, `system_setting`, `id_sequence_master`, `country`, `document_master`,
  `master_data`, `state`, `district`, `city_village`, `postal_code`) —
  `deleted_at` is a plain timestamp, not an audit-actor FK, so unlike
  `deleted_by_sangha_sevi_pk` above it doesn't need to wait for Pass 2. `field_change_log`
  deliberately has neither column — it is an append-only log.
- **`document_master`** — owned by Foundation (DOC-ARCH-001); logical design from Person §54.
  Person-specific FKs (`person_pk`, `uploaded_by_sangha_sevi_pk`) deferred to Pass 2.
- **`field_change_log`** — stores references as UUID values without FK constraints to avoid
  circular dependencies. Application layer enforces referential integrity.
- **PIN Code Model (Amendment)** — `postal_code` added to support searchable geographic
  hierarchy and map visualization. PIN codes have an explicit `state_pk` FK for direct
  administrative ownership (PIN → State is always deterministic). `city_village` carries a
  direct `postal_code_pk` FK (one city/village → one PIN, replacing an earlier M:N junction
  table design). **Note:** the implemented `organization` table
  (`database/ddl/02_organization/03_organization.sql`) also consumes this model — it has a
  `postal_code_pk UUID` FK to `nss.postal_code` (plus `district_pk`/`state_pk`/`country_pk`/
  `city_village_pk` FKs and standalone `latitude`/`longitude` columns for map-based search).
- **Simplified Geography Model (Amendment, 2026-10-02)** — the `post_office` table (added
  2026-10-02 as an interim office-grain child of `postal_code`; **reinstated 2026-10-03** as
  `13_post_office.sql`, see above) was retired the same day in
  favor of resolving district directly on `city_village`. `postal_code` was simplified in
  lockstep: `country_pk` dropped (redundant via `state_pk`), `post_office_name` dropped (no
  source once `post_office` was retired), and uniqueness relaxed from
  `(country_pk, postal_code)` to `(postal_code)` alone — a dominant state is chosen for the
  small number of PINs that legitimately span state lines. Seed data was regenerated
  all-India from 4 government-coded source files (LGD district codes, ULB local-body
  mapping, the village directory, and the pincode-to-village mapping) rather than the
  previously used India Post PDF/CSV directory.
- **Supersedes** — this replaces the previous `country_master`, `state_province_master`,
  `district_region_master`, `city_village_master` tables from the prototype iteration, and an
  earlier `city_village_postal_code_map` M:N junction table (retired in favor of the direct
  `city_village.postal_code_pk` FK above).
