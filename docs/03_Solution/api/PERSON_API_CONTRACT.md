# Person API Contract — Tier 3 Read-Only

| Field       | Value                                          |
|-------------|------------------------------------------------|
| Document    | PERSON_API_CONTRACT                            |
| Version     | 1.0                                            |
| Tier        | 3 — Person                                     |
| Authority   | SOL-PER-001 through SOL-PER-005                |
| Status      | DRAFT                                          |

---

## 1. Purpose

This document defines the API contract for the Tier 3 Person read-only API.
All endpoints are GET-only. No authentication (*at v0.9.0 — see the Tier 5 note below*). `nss_db_backend` connects with
SELECT-only privileges.

The Person API exposes individual member/participant records within the NSS
system — demographics, contact details, addresses, and a trigram-based search
facility. Sensitive identity data (Aadhaar) is protected by a three-layer
defence: encrypted at rest (DDL), never selected by the API (SQL), and only
the last 4 digits returned for masked display.

Write operations (POST/PATCH/DELETE) are deferred to Tier 5 when authenticated
administration and authorization exist.

> **Tier 5 update (v0.11.0):**
> all 4 endpoints now require a JWT. `GET /persons` (list) and `GET /search` require
> `require_permission("PERSON_VIEW")`; `GET /persons/{pk}` and `GET /persons/{pk}/addresses`
> use `get_current_user` plus an ownership check (`_require_person_view`) — the person
> themself, or a holder of `PERSON_VIEW`. List endpoints accept `sort_by`/`sort_dir`
> (whitelisted, 422 otherwise). *(Superseded 2026-11-04 by GDR-011, Proposed: `aadhaar_last4`
> and the new `aadhaar_full_on_file` flag are null unless the caller is the person or holds
> `PERSON_VIEW_SENSITIVE` in admin scope, and `GET /persons/{pk}/aadhaar` returns the decrypted
> number to those holders only, audited. `aadhaar_encrypted`/`aadhaar_hash` are still never returned.)* Person *writes* are not
> in this router: they live in `api/routers/admin.py` (`POST /api/v1/admin/persons`) and
> `api/routers/registration.py`. Responses gain 401/403 beyond the statuses listed below.

---

## 2. Conventions

### From Tier 0 (Carried Forward)

- **Prefix:** `/api/v1/person`
- **Tag:** `person`
- **Router:** `api/routers/person.py`
- **Schemas:** `api/schemas/person.py`
- **DB access:** `conn = Depends(get_connection)` with raw psycopg2
- **Response models:** Pydantic v2 `BaseModel` — no `ConfigDict(from_attributes=True)`
  (raw psycopg2 returns dictionaries, not ORM objects)
- **Audit columns excluded:** `created_at`, `updated_at`, `deleted_at`,
  `created_by_sangha_sevi_pk`, `updated_by_sangha_sevi_pk`,
  `deleted_by_sangha_sevi_pk` are never returned in API responses
- **Active-only by default:** All list endpoints filter `WHERE is_active = TRUE`
- **UUID path parameters:** Validated by FastAPI/Pydantic (422 on malformed UUID)
- **404 on missing:** `HTTPException(status_code=404)` when a PK lookup yields no row
- **Shared helpers:** `api/helpers.py` provides `rows_to_models`, `row_to_model`,
  `DEFAULT_LIMIT` (100), `MAX_LIMIT` (500) — shared across all routers

### New for Tier 3

- **Shared SQL fragments:** `_PERSON_DETAIL_SELECT` (22 fields, 4 LEFT JOINs),
  `_PERSON_SUMMARY_SELECT` (16 fields, 3 LEFT JOINs), and `_ADDRESS_SELECT`
  (17 fields, 6 JOINs) centralise column selection across endpoints
- **Sensitive data exclusion (PER-BR-081):** `aadhaar_encrypted` (BYTEA) and
  `aadhaar_hash` (VARCHAR) are present in the DDL but deliberately excluded
  from all SQL SELECT fragments and all Pydantic response models. Only
  `aadhaar_last4` (CHAR(4)) is returned — and only in `PersonResponse`
  (detail), not in `PersonSummaryResponse` (list/search)
- **Master-data resolution via JOINs:** Gender, marital status, blood group,
  emergency relationship, and address type are resolved to `value_code` +
  `value_name` via LEFT JOINs on `nss.master_data`, avoiding N+1 lookups
- **Combinable filters:** `gender_code`, `marital_status_code`, and
  `blood_group_code` query parameters are independently combinable
  (`if`/`if`/`if`, not `if`/`elif`)
- **Pagination:** List endpoint supports `limit` (1–500, default 100) and
  `offset` (≥0, default 0) via shared `DEFAULT_LIMIT`/`MAX_LIMIT` constants.
  FastAPI `Query(ge=1, le=MAX_LIMIT)` enforces bounds at the framework level
  (422 on violation)
- **Trigram search:** Uses PostgreSQL `pg_trgm` extension for fuzzy name
  matching with `similarity()` ranking, plus ILIKE prefix matching on
  `person_id`, `mobile_number`, and `email`. Email-like queries use
  `re.split(r'[.@]', q)[0]` for trigram params to prevent false
  positives. Hardcoded `LIMIT 50`
- **Person existence guard:** The addresses endpoint verifies the person
  exists before querying, preventing `200 []` for non-existent persons

### Endpoint Classification

| Class                          | Endpoints                        | Consumer               |
|--------------------------------|----------------------------------|------------------------|
| Core person data               | persons (list, detail)           | Application / frontend |
| Address data                   | person addresses                 | Application / frontend |
| Search                         | trigram search                   | Search UI              |

---

## 3. Endpoint Catalogue

### 3.1 Core Person Data

Both endpoints below use shared SQL fragments (`_PERSON_SUMMARY_SELECT` for
list, `_PERSON_DETAIL_SELECT` for detail) to ensure consistent column
ordering and avoid duplication.

#### 3.1.1 List Persons

```
GET /api/v1/person/persons
```

Returns all active persons with resolved master-data context. Compact summary
format — no Aadhaar, emergency, or photo fields.

**Query Parameters:**

| Param                  | Type   | Required | Default | Description                            |
|------------------------|--------|----------|---------|----------------------------------------|
| `gender_code`          | string | No       | —       | Filter by gender value_code (e.g. MALE)|
| `marital_status_code`  | string | No       | —       | Filter by marital status value_code    |
| `blood_group_code`     | string | No       | —       | Filter by blood group value_code       |
| `limit`                | int    | No       | 100     | Max rows (1–500)                       |
| `offset`               | int    | No       | 0       | Rows to skip (≥0)                      |

All three filters are independently combinable. A non-matching filter returns
`[]`, not an error. `limit` and `offset` are validated by FastAPI — `limit=0`
or `limit=501` returns 422.

**Response:** `200 OK`

```json
[
  {
    "person_pk": "uuid",
    "person_id": "PER-0001",
    "first_name": "Ramesh",
    "middle_name": null,
    "last_name": "Mishra",
    "date_of_birth": "1965-03-15",
    "date_of_death": null,
    "gender_code": "MALE",
    "gender_name": "Male",
    "marital_status_code": "MARRIED",
    "marital_status_name": "Married",
    "blood_group_code": "O_POSITIVE",
    "blood_group_name": "O+",
    "country_phone_code": "+91",
    "mobile_number": "9876543210",
    "email": "ramesh@example.com",
    "is_active": true
  }
]
```

**Tier 3 state:** No seed data — returns `[]`. Persons will appear when
write endpoints are added (Tier 5+) or test data is inserted manually.

**SQL Pattern (`_PERSON_SUMMARY_SELECT`):**

```sql
SELECT p.person_pk, p.person_id,
       p.first_name, p.middle_name, p.last_name,
       p.date_of_birth, p.date_of_death,
       g.value_code AS gender_code,
       g.value_name AS gender_name,
       ms.value_code AS marital_status_code,
       ms.value_name AS marital_status_name,
       bg.value_code AS blood_group_code,
       bg.value_name AS blood_group_name,
       p.country_phone_code, p.mobile_number, p.email,
       p.is_active
FROM   nss.person p
LEFT JOIN nss.master_data g
       ON g.master_data_pk = p.gender_master_data_pk
LEFT JOIN nss.master_data ms
       ON ms.master_data_pk = p.marital_status_master_data_pk
LEFT JOIN nss.master_data bg
       ON bg.master_data_pk = p.blood_group_master_data_pk
WHERE  p.is_active = TRUE
ORDER BY p.first_name, p.last_name
LIMIT %s OFFSET %s
```

When `gender_code` is provided, add: `AND g.value_code = %s`
When `marital_status_code` is provided, add: `AND ms.value_code = %s`
When `blood_group_code` is provided, add: `AND bg.value_code = %s`

---

#### 3.1.2 Get Person by PK

```
GET /api/v1/person/persons/{person_pk}
```

Returns a single person with full resolved context — emergency contact and photo FK, plus
`aadhaar_last4` (4 digits) and `aadhaar_full_on_file` (bool), both **null** unless the caller is
the person themself or holds `PERSON_VIEW_SENSITIVE` within admin scope over the person
(GDR-011, Proposed). Never returns `aadhaar_encrypted` or `aadhaar_hash`. The full number is
only available from `GET /api/v1/person/persons/{person_pk}/aadhaar` (decrypted digits,
`PERSON_VIEW_SENSITIVE` + admin scope, audited, rate limited).

**Path Parameters:**

| Param       | Type | Required | Description        |
|-------------|------|----------|--------------------|
| `person_pk` | UUID | Yes      | Person primary key |

**Response:** `200 OK` — single `PersonResponse` (28 fields)

**Error Responses:**

| Status | When                                |
|--------|-------------------------------------|
| 404    | PK not found or inactive            |
| 422    | Malformed UUID                      |

**SQL Pattern (`_PERSON_DETAIL_SELECT`):**

```sql
SELECT p.person_pk, p.person_id,
       p.first_name, p.middle_name, p.last_name,
       p.date_of_birth, p.date_of_death,
       p.gender_master_data_pk,
       g.value_code   AS gender_code,
       g.value_name   AS gender_name,
       p.marital_status_master_data_pk,
       ms.value_code  AS marital_status_code,
       ms.value_name  AS marital_status_name,
       p.blood_group_master_data_pk,
       bg.value_code  AS blood_group_code,
       bg.value_name  AS blood_group_name,
       p.country_phone_code, p.mobile_number, p.email,
       p.aadhaar_last4,
       p.photo_document_master_pk,
       p.emergency_contact_name,
       p.emergency_contact_phone,
       p.emergency_relationship_master_data_pk,
       er.value_code  AS emergency_relationship_code,
       er.value_name  AS emergency_relationship_name,
       p.remarks, p.is_active
FROM   nss.person p
LEFT JOIN nss.master_data g
       ON g.master_data_pk = p.gender_master_data_pk
LEFT JOIN nss.master_data ms
       ON ms.master_data_pk = p.marital_status_master_data_pk
LEFT JOIN nss.master_data bg
       ON bg.master_data_pk = p.blood_group_master_data_pk
LEFT JOIN nss.master_data er
       ON er.master_data_pk = p.emergency_relationship_master_data_pk
WHERE  p.person_pk = %s AND p.is_active = TRUE
```

---

### 3.2 Address Data

#### 3.2.1 List Person Addresses

```
GET /api/v1/person/persons/{person_pk}/addresses
```

Returns all active addresses for a given person with resolved location
context through the geographic chain: address type → city/village + postal
code (via junction) → district → state → country.

404 if the person does not exist.

**Path Parameters:**

| Param       | Type | Required | Description        |
|-------------|------|----------|--------------------|
| `person_pk` | UUID | Yes      | Person primary key |

**Response:** `200 OK` — list of `PersonAddressResponse`

**Error Responses:**

| Status | When                                     |
|--------|------------------------------------------|
| 404    | `person_pk` not found or inactive        |
| 422    | Malformed UUID                           |

**Design note:** The two-step pattern (existence check + address query)
prevents a non-existent person from silently returning `200 []`, which
would be indistinguishable from "person exists but has no addresses."

**SQL Pattern (`_ADDRESS_SELECT`):**

```sql
-- Step 1: Verify person exists
SELECT 1 FROM nss.person
WHERE  person_pk = %s AND is_active = TRUE

-- Step 2: Fetch addresses
SELECT pa.person_address_pk, pa.person_pk,
       pa.address_type_master_data_pk,
       at.value_code  AS address_type_code,
       at.value_name  AS address_type_name,
       pa.address_line_1, pa.address_line_2, pa.landmark,
       pa.city_village_postal_code_map_pk,
       cv.city_village_name, pc.postal_code,
       d.district_name, s.state_name, c.country_name,
       pa.is_primary, pa.remarks, pa.is_active
FROM   nss.person_address pa
JOIN   nss.master_data at
       ON at.master_data_pk = pa.address_type_master_data_pk
JOIN   nss.city_village_postal_code_map cvm
       ON cvm.city_village_postal_code_map_pk
          = pa.city_village_postal_code_map_pk
LEFT JOIN nss.city_village cv
       ON cv.city_village_pk = cvm.city_village_pk
LEFT JOIN nss.postal_code pc
       ON pc.postal_code_pk = cvm.postal_code_pk
LEFT JOIN nss.district d
       ON d.district_pk = cv.district_pk
LEFT JOIN nss.state s
       ON s.state_pk = d.state_pk
LEFT JOIN nss.country c
       ON c.country_pk = s.country_pk
WHERE  pa.person_pk = %s AND pa.is_active = TRUE
ORDER BY pa.is_primary DESC, at.value_name
```

---

### 3.3 Search

#### 3.3.1 Search Persons

```
GET /api/v1/person/search
```

Searches active persons by name, person_id, mobile number, or email. Uses
PostgreSQL trigram similarity (`pg_trgm`) on first_name and last_name for
fuzzy matching, plus ILIKE prefix matching on `person_id`,
`mobile_number`, and `email`. For email-like queries (containing `.` or
`@`), the trigram comparison uses only the name portion before the
delimiter to prevent false positives. Results ranked by trigram similarity
(best match first), capped at 50 results.

**Query Parameters:**

| Param | Type   | Required | Constraints    | Description                              |
|-------|--------|----------|----------------|------------------------------------------|
| `q`   | string | Yes      | min_length = 2 | Search term                              |

**Response:** `200 OK` — list of `PersonSummaryResponse` (max 50)

**Error Responses:**

| Status | When                                     |
|--------|------------------------------------------|
| 422    | `q` missing or fewer than 2 characters   |

**SQL Pattern:**

```sql
_PERSON_SUMMARY_SELECT
WHERE p.is_active = TRUE
  AND (
      similarity(p.first_name, %s) > 0.45
      OR similarity(p.last_name, %s) > 0.45
      OR p.person_id ILIKE %s
      OR p.mobile_number ILIKE %s
      OR p.email ILIKE %s
  )
ORDER BY similarity(p.first_name, %s) DESC,
         p.first_name, p.last_name
LIMIT 50
```

`similarity()` is `pg_trgm`'s explicit similarity function, called directly with a
`> 0.45` threshold rather than the `%` operator (which relies on the session's
`pg_trgm.similarity_threshold` GUC) — this matches the Membership module's identical
threshold, making the two modules' fuzzy-match behavior predictable and independent
of any session-level GUC configuration. The ILIKE pattern is `f"{q}%"` (prefix match), passed as a `%s`
parameter — never interpolated into the SQL string. For trigram parameters,
email-like queries use `name_q = re.split(r'[.@]', q)[0]` to extract the
name portion before `.` or `@`.

---

## 4. Response Schema Summary

### Pydantic Models (api/schemas/person.py)

| Model                    | Endpoint(s)                | Field Count |
|--------------------------|----------------------------|-------------|
| `PersonResponse`         | detail                     | 28          |
| `PersonSummaryResponse`  | list, search               | 17          |
| `PersonAddressResponse`  | addresses                  | 17          |

### PersonResponse — 28 Fields by Group

| Group                | Fields                                                                                          |
|----------------------|-------------------------------------------------------------------------------------------------|
| Identity (2)         | person_pk, person_id                                                                            |
| Demographics (5)     | first_name, middle_name, last_name, date_of_birth, date_of_death                                |
| Gender (3)           | gender_master_data_pk, gender_code, gender_name                                                 |
| Marital Status (3)   | marital_status_master_data_pk, marital_status_code, marital_status_name                         |
| Blood Group (3)      | blood_group_master_data_pk, blood_group_code, blood_group_name                                  |
| Contact (3)          | country_phone_code, mobile_number, email                                                        |
| Sensitive (1)        | aadhaar_last4                                                                                   |
| Photo (1)            | photo_document_master_pk                                                                        |
| Emergency (5)        | emergency_contact_name, emergency_contact_phone, emergency_relationship_master_data_pk, emergency_relationship_code, emergency_relationship_name |
| Other (1)            | remarks                                                                                         |
| Lifecycle (1)        | is_active                                                                                       |

### PersonSummaryResponse — Compact List/Search Format

Excludes from `PersonResponse`: all `*_master_data_pk` FK fields,
`aadhaar_last4`, `photo_document_master_pk`, all emergency fields, `remarks`.
Retains resolved `*_code` / `*_name` pairs for display.

### PersonAddressResponse — 17 Fields by Group

| Group                | Fields                                                                        |
|----------------------|-------------------------------------------------------------------------------|
| Identity (2)         | person_address_pk, person_pk                                                  |
| Address Type (3)     | address_type_master_data_pk, address_type_code, address_type_name             |
| Address (3)          | address_line_1, address_line_2, landmark                                      |
| Location (6)         | city_village_postal_code_map_pk, city_village_name, postal_code, district_name, state_name, country_name |
| Flags (3)            | is_primary, remarks, is_active                                                |

### Fields Deliberately Excluded

| Field                          | Reason                                                  |
|--------------------------------|---------------------------------------------------------|
| `aadhaar_encrypted`            | Sensitive PII — never exposed (PER-BR-081)              |
| `aadhaar_hash`                 | Sensitive PII — never exposed (PER-BR-081)              |
| `created_at`                   | System audit — not API-facing (Tier 0 rule)             |
| `updated_at`                   | System audit — not API-facing                           |
| `deleted_at`                   | System audit — not API-facing                           |
| `created_by_sangha_sevi_pk`    | Audit actor FK — deferred to Tier 5 (needs auth)        |
| `updated_by_sangha_sevi_pk`    | Audit actor FK — deferred to Tier 5                     |
| `deleted_by_sangha_sevi_pk`    | Audit actor FK — deferred to Tier 5                     |

---

## 5. Aadhaar Data Protection Strategy

The Person module introduces the project's first sensitive PII handling.
Three-layer defence-in-depth:

| Layer      | Mechanism                                                          |
|------------|--------------------------------------------------------------------|
| DDL        | `aadhaar_encrypted BYTEA` (pgcrypto `pgp_sym_encrypt`), `aadhaar_hash VARCHAR(64)` (SHA-256), `aadhaar_last4 CHAR(4)` with CHECK `~ '^\d{4}$'` |
| SQL/API    | `_PERSON_DETAIL_SELECT` and `_PERSON_SUMMARY_SELECT` never SELECT `aadhaar_encrypted` or `aadhaar_hash`. No Pydantic model includes them |
| UI         | Displays as "XXXX XXXX {last4}" via Alpine.js `x-text` (auto-escaped). Zero uses of `x-html` or `innerHTML` |

**Tier 3 (read-only):** The encrypted and hash columns are unreadable — `nss_db_backend`
has only SELECT privilege, and the application layer never selects them.

**Tier 5+ (write):** Encryption key management strategy is a deferred concern.
The key must never be stored in the database or `.env` alongside `DB_PASSWORD`.

---

## 6. Endpoint Count Summary

| Group              | Endpoints | Tables Covered                    |
|--------------------|-----------|-----------------------------------|
| Core Persons       | 2         | person (list, detail)             |
| Addresses          | 1         | person_address                    |
| Search             | 1         | person (trigram)                  |
| **Total**          | **4**     | **2 tables exposed**              |

---

## 7. Error Responses

Carried forward from Tier 0, extended for Person:

| Status | When                                      | Body                                     |
|--------|-------------------------------------------|------------------------------------------|
| 200    | Success                                   | Response model (list or single)          |
| 404    | Person PK — not found or inactive         | `{"detail": "Person not found"}`         |
| 422    | Malformed UUID or invalid query parameter | FastAPI validation error                 |
| 422    | `limit=0`, `limit=501`, `offset=-1`      | FastAPI validation error (ge/le bounds)  |
| 422    | Search `q` missing or < 2 characters      | FastAPI validation error                 |

---

## 8. Implementation File Map

```
api/
  helpers.py                        <- Shared cursor→Pydantic helpers + pagination constants
  routers/
    person.py                       <- 4 endpoint handlers + 3 SQL fragments
  schemas/
    person.py                       <- 3 Pydantic response models
database/
  ddl/03_person/
    02_person.sql                   (28 columns, 15 FKs, CHECK constraints)
    03_person_address.sql           (person_address table)
tests/
  test_person.py                    <- 61 integration tests
frontend/
  admin.html                        <- Person UI: Person Directory tab
                                       (replaces the retired person.html)
  assets/js/admin.js                <- Alpine.js data component
                                       (replaces the retired person.js)
docs/
  03_Solution/modules/03_person/
    01_person_design.md             <- Module design (FROZEN v2.0.0)
    02_person_erd.md                <- ERD diagrams (FROZEN v2.0.0)
    03_person_lifecycle.md          <- Entity lifecycle (FROZEN v2.0.0)
    04_person_business_rules.md     <- Business rules (FROZEN v2.0.0)
    05_person_table_design.md       <- Table design (FROZEN v2.0.0)
  03_Solution/code_explanations/
    TIER3_SECURITY_AUDIT.md         <- Security audit (18 checks)
```

---

## 9. Master-Data Dependencies

Person references Foundation `master_data` for four domain concepts:

| Person FK                                 | Category Code       | Seeded Values                                |
|-------------------------------------------|---------------------|----------------------------------------------|
| `gender_master_data_pk`                   | GENDER              | MALE, FEMALE, TRANSGENDER, PREFER_NOT_TO_SAY |
| `marital_status_master_data_pk`           | MARITAL_STATUS      | SINGLE, MARRIED, WIDOWED, DIVORCED, SEPARATED |
| `blood_group_master_data_pk`              | BLOOD_GROUP         | A_POSITIVE, A_NEGATIVE, B_POSITIVE, B_NEGATIVE, AB_POSITIVE, AB_NEGATIVE, O_POSITIVE, O_NEGATIVE |
| `emergency_relationship_master_data_pk`   | RELATIONSHIP_TYPE   | FATHER, MOTHER, SPOUSE, SON, DAUGHTER, SIBLING, GUARDIAN, OTHER |

Address type (`address_type_master_data_pk` on `person_address`) also
references `master_data` under the `ADDRESS_TYPE` category.

---

## 10. Future (Tier 5+)

When Authentication + Administration arrives:

```
Authenticated user
       |
ERP role + permission + scope
       |
POST   /api/v1/person/persons                     (create)
PATCH  /api/v1/person/persons/{pk}                 (update)
DELETE /api/v1/person/persons/{pk}                 (soft-delete)
POST   /api/v1/person/persons/{pk}/addresses       (add address)
PATCH  /api/v1/person/persons/{pk}/addresses/{apk} (update address)
DELETE /api/v1/person/persons/{pk}/addresses/{apk} (soft-delete)
```

Write operations will include:
- Aadhaar encryption (pgcrypto `pgp_sym_encrypt`) + hash (SHA-256) + last-4 extraction
- Aadhaar uniqueness check via `aadhaar_hash` (duplicate detection without decryption)
- Contact field validation (email format, phone format, country code)
- `person_id` auto-generation via `id_sequence_master`
- Photo upload → `document_master` FK linkage
- Person lifecycle management (is_active toggle, date_of_death recording)

The DB role (`nss_db_backend`) will be granted narrowly scoped write privileges
at that time — not before.

---

## 11. Non-Breaking Extension Points

These can be added later without changing existing contracts:

| Extension               | Mechanism                                                  |
|-------------------------|------------------------------------------------------------|
| Include inactive        | Add `?include_inactive=true` (auth-gated)                  |
| Address pagination      | Add `limit`/`offset` to addresses endpoint                 |
| Search pagination       | Replace hardcoded `LIMIT 50` with query parameter          |
| Person count            | Add `GET /persons/count` with same filters                 |

**Deliberately excluded from this list:**

| Capability               | Why                                                     |
|--------------------------|---------------------------------------------------------|
| Include inactive records | Authorization concern — admin-only when auth exists     |
| Aadhaar search           | Security concern — never expose hash-based lookup via API |
| Bulk person export       | Data protection concern — requires audit trail + auth   |
| Nested address JSON      | Flat list is the chosen pattern; detail view fetches one |
| Membership/role data     | Deferred to Tier 4 (sangha_sevi + role assignment)      |
