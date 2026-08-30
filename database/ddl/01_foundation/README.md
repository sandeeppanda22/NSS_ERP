# database/ddl/01_foundation/

Foundation Module DDL — 12 tables (Depths 0–4).

Authority: SOL-ARCH-010 (DDL Creation Order) + Amendment (PIN Code Geographic
Model, 2026-08-28), SOL-FND-004 (Foundation Table Design)

## File Execution Order

Execute files in numeric order. Each file depends only on tables created
by earlier-numbered files in this directory.

| # | File | Table | Depth | Global Seq |
|--:|------|-------|------:|-----------:|
| 01 | `01_extensions.sql` | — (pgcrypto, pg_trgm, btree_gin) | — | — |
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
| 12 | `12_postal_code.sql` | `postal_code` | 2 | #87 (amendment) |
| 13 | `13_city_village_postal_code_map.sql` | `city_village_postal_code_map` | 4 | #88 (amendment) |

**Note:** Files 12–13 depend on `country`+`state` (Depth 0/1, updated 2026-08-30 to add a
direct `state_pk` FK to `postal_code`) and `city_village` (Depth 3) respectively. They are
numbered after the original 11 files for clarity but
execute correctly in sequence because their dependencies are already created
by earlier files.

## Execution Command

```bash
# As NSS_ADMIN against the nss_erp database:
for f in database/ddl/01_foundation/0*.sql database/ddl/01_foundation/1*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done
```

---

## Table Descriptions

### 1. `master_category` (Depth 0, #1 of 88)

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

### 2. `system_setting` (Depth 0, #2 of 88)

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

### 3. `id_sequence_master` (Depth 0, #3 of 88)

Configuration registry for generating human-readable business IDs. Each row
defines a sequence with a prefix and zero-padded counter. The application layer
reads `current_value`, increments it, and formats the ID as
`{prefix}{zero-padded current_value}` (e.g. `SKH00000001` for the first Sakha).

Unique organizations (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA) do not use
sequences — they receive fixed codes directly from seed data.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `id_sequence_master_pk` | UUID | PK, auto | Internal primary key |
| `sequence_code` | VARCHAR(50) | UNIQUE, NOT NULL | Sequence identifier (e.g. `PERSON`, `SAKHA`) |
| `sequence_name` | VARCHAR(100) | UNIQUE, NOT NULL | Human-readable name |
| `prefix` | VARCHAR(20) | NOT NULL | ID prefix (e.g. `P`, `SKH`, `ANC`) |
| `current_value` | BIGINT | NOT NULL, default 0 | Last used counter value; CHECK >= 0 |
| `padding_length` | INTEGER | NOT NULL, default 8 | Zero-padding width; CHECK 4–12 |
| `description` | TEXT | NULL | Optional description |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Indexes:** `sequence_code`, `is_active`

---

### 4. `country` (Depth 0, #4 of 88)

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

### 5. `document_master` (Depth 0, #5 of 88)

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

### 6. `field_change_log` (Depth 0, #6 of 88)

Field-level audit trail. Records individual column-value changes across any
table in the ERP. The application layer writes to this table whenever a tracked
field is modified, capturing old value, new value, who changed it, and why.

No FK constraints — `table_name` and `record_pk` are stored as plain values
(VARCHAR + UUID) to avoid circular dependencies. `changed_by_sangha_sevi_pk`
is also stored as a raw UUID without FK constraint. Referential integrity is
enforced by the application layer.

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `field_change_log_pk` | UUID | PK, auto | Internal primary key |
| `table_name` | VARCHAR(100) | NOT NULL | Name of the table that was changed |
| `record_pk` | UUID | NOT NULL | PK of the changed record |
| `field_name` | VARCHAR(100) | NOT NULL | Column name that changed |
| `old_value` | TEXT | NULL | Previous value (NULL for new records) |
| `new_value` | TEXT | NULL | New value (NULL for deletions) |
| `change_reason` | TEXT | NULL | Why the change was made |
| `changed_at` | TIMESTAMPTZ | NOT NULL, auto | When the change occurred |
| `changed_by_sangha_sevi_pk` | UUID | NULL | Who made the change (no FK — application-enforced) |

**Indexes:** `(table_name, record_pk)`, `changed_at`, `(table_name, field_name)`

---

### 7. `master_data` (Depth 1, #18 of 88)

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

### 8. `state` (Depth 1, #19 of 88)

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

### 9. `district` (Depth 2, #26 of 88)

Third level of the geographic hierarchy. Stores districts within a state.
Seeded with all Indian districts (~770); non-India districts populated at
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

**Unique:** `(state_pk, district_code)`, `(state_pk, district_name)`

**Indexes:** `state_pk`, `is_active`, `district_name` (GIN trigram)

---

### 10. `city_village` (Depth 3, #32 of 88)

Fourth level of the geographic hierarchy. Stores individual localities
(cities, towns, villages) within a district. Not seeded — populated during
deployment or data migration.

**FK:** `district_pk` → `district`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `city_village_pk` | UUID | PK, auto | Internal primary key |
| `district_pk` | UUID | FK, NOT NULL | Parent district |
| `city_village_code` | VARCHAR(20) | NOT NULL | Locality code |
| `city_village_name` | VARCHAR(150) | NOT NULL | Full locality name |
| `city_village_type` | VARCHAR(20) | NOT NULL | CHECK: `CITY`, `TOWN`, `VILLAGE` |
| `display_order` | INTEGER | NOT NULL, default 0 | UI ordering within district |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Unique:** `(district_pk, city_village_code)`, `(district_pk, city_village_name)`

**Indexes:** `district_pk`, `is_active`, `city_village_name` (GIN trigram)

---

### 11. `postal_code` (Depth 2, #87 of 88 — amendment, updated 2026-08-30)

PIN code / postal code reference table. Country-scoped with a direct `state_pk`
FK for administrative ownership (PIN → State is always deterministic, added
2026-08-30). One PIN code can serve multiple cities/villages (M:N via the map
table). Supports address validation, autocomplete, and map-based search
("find nearby Sanghas").

**FKs:** `country_pk` → `country`, `state_pk` → `state`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `postal_code_pk` | UUID | PK, auto | Internal primary key |
| `country_pk` | UUID | FK, NOT NULL | Country this PIN code belongs to |
| `state_pk` | UUID | FK, NOT NULL | State this PIN code belongs to (reference only, not part of the unique key) |
| `postal_code` | VARCHAR(20) | NOT NULL | The PIN / postal code value (e.g. `751024`) |
| `post_office_name` | VARCHAR(150) | NULL | Name of the post office serving this code |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Last modification timestamp |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-delete flag |

**Unique:** `(country_pk, postal_code)` — a PIN is globally unique within a country's postal system

**Indexes:** `country_pk`, `state_pk`, `postal_code`, `is_active`,
`post_office_name` (GIN trigram, partial WHERE NOT NULL)

---

### 12. `city_village_postal_code_map` (Depth 4, #88 of 88 — amendment)

Junction table implementing the M:N relationship between `city_village` and
`postal_code`. One PIN code can serve multiple localities (e.g. a post office
covers several villages); one locality can have multiple PIN codes (e.g. a
large city with multiple post offices).

**FKs:** `city_village_pk` → `city_village`, `postal_code_pk` → `postal_code`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `city_village_postal_code_map_pk` | UUID | PK, auto | Internal primary key |
| `city_village_pk` | UUID | FK, NOT NULL | The locality |
| `postal_code_pk` | UUID | FK, NOT NULL | The PIN/postal code |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Row creation timestamp |

**Unique:** `(city_village_pk, postal_code_pk)` — no duplicate mappings

**Indexes:** `city_village_pk`, `postal_code_pk`

---

## Design Decisions

- **No audit-actor FKs** — `created_by_sangha_sevi_pk` / `updated_by_sangha_sevi_pk` /
  `deleted_by_sangha_sevi_pk` are NOT included in Foundation tables. They will be added
  via ALTER TABLE in Pass 2 after `sangha_sevi` exists (SOL-ARCH-010 §5).
- **Soft-delete backfill (2026-08-30)** — `deleted_at TIMESTAMPTZ NULL` plus a
  `(is_active = TRUE AND deleted_at IS NULL) OR (is_active = FALSE AND deleted_at IS NOT NULL)`
  CHECK constraint added to all 10 tables that carry `is_active`
  (`master_category`, `system_setting`, `id_sequence_master`, `country`, `document_master`,
  `master_data`, `state`, `district`, `city_village`, `postal_code`) — `deleted_at` is a plain
  timestamp, not an audit-actor FK, so unlike `deleted_by_sangha_sevi_pk` above it doesn't need
  to wait for Pass 2. `field_change_log` and `city_village_postal_code_map` deliberately have
  neither column — the former is an append-only log, the latter a pure M:N junction table.
- **`document_master`** — owned by Foundation (DOC-ARCH-001); logical design from Person §54.
  Person-specific FKs (`person_pk`, `uploaded_by_sangha_sevi_pk`) deferred to Pass 2.
- **`field_change_log`** — stores references as UUID values without FK constraints to avoid
  circular dependencies. Application layer enforces referential integrity.
- **PIN Code Model (Amendment 2026-08-28, updated 2026-08-30)** — `postal_code` and
  `city_village_postal_code_map` added to support searchable geographic hierarchy and map
  visualization. PIN codes have an explicit `state_pk` FK for direct administrative ownership
  (PIN → State is always deterministic); uniqueness is `(country_pk, postal_code)`.
  M:N relationship to `city_village` via mapping table. Organization stores `postal_code_pk`
  (FK to `postal_code`) plus `latitude`/`longitude` NUMERIC(10,7) for exact coordinates.
- **Supersedes** — this replaces the previous `country_master`, `state_province_master`,
  `district_region_master`, `city_village_master` tables from the prototype iteration.
  The new `postal_code` and `city_village_postal_code_map` tables preserve the same
  M:N model from the prototype but with corrected naming.
