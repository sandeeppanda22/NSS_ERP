# Organization API Contract — Tier 2 Read-Only

| Field       | Value                                          |
|-------------|------------------------------------------------|
| Document    | ORGANIZATION_API_CONTRACT                      |
| Version     | 1.2                                            |
| Tier        | 2 — Organization                               |
| Authority   | SOL-ARCH-010, SOL-ORG-005 SS19-SS52            |
| Status      | DRAFT                                          |

> **v1.1 (2026-09-12):** `organization_type_master` and `organization_status_master`
> are retired. `types` and `statuses` are now backed by Foundation's shared
> `nss.master_data`/`nss.master_category` tables (categories `ORGANIZATION_TYPE`
> and `STATUS`). `organization_type_master_data_pk` and `status_master_data_pk`
> replace the old dedicated-table FKs on `organization`. `OrganizationStatusResponse`
> is renamed to `StatusResponse` (fields `organization_status_*` → `status_*`).
> Type count is now 10 (was 8); status count is now 13 (was 6) since `STATUS` is a
> unified ERP-wide category shared across modules.

> **v1.2 (Tier 4, on top of Family + Membership):** New endpoint
> `GET /organizations/{organization_pk}/children-stats` (§3.2.4) — Organization goes from 6
> to 7 endpoints. Aggregates family/member/person counts per direct child by recursively
> walking descendant Sakhas and applying the FAM-036 majority-rule "effective Sakha"
> computation also used independently by Family's `/families/{pk}/sakha-alignment` endpoint
> (see `docs/03_Solution/api/API_CONTRACT.md` §7 — Tier 4 Family, and
> `docs/03_Solution/modules/family/04_family_business_rules.md` § FAM-036). New response
> model `OrgChildStatsResponse`.


> **Amendment (2026-10-30, owner-directed, GDR-005/GDR-007):** `GET /organization/types` now returns 14 types (adds `ADVISORY_BOARD`). The `ADVISORY_BOARD` organization's `organization_name` is immutable (422 on change). Re-parenting a `SAKHA_SANGHA` or `SAKHA_ASANA` through `PATCH /admin/organizations/{pk}` returns HTTP 202 with an approval request unless the actor is a Kendra Governing Body member or the `NSS_ERP_ADMIN` super administrator (GDR-007). A second active `KENDRA`/`NILACHALA_KUTIRA`/`SMRUTI_MANDIRA`/`ADVISORY_BOARD`, or a second central (Kendra-parented) `MAHILA_SANGHA`, is refused with 422 on create and on re-parenting (GDR-005 item 7).

> **Amendment (2026-10-31, owner-directed, GDR-008):** the type-to-type parent matrix (ORG-BR-091/092/094) is widened: `KUMARI_SANGHA`, `SEVAK_SANGHA`, the local per-Sakha `MAHILA_SANGHA` and `PARIBARIK_ASANA` may be parented by a Sakha-like organization — `SAKHA_SANGHA` **or** `SAKHA_ASANA` (the `MAHILA_SANGHA` `KENDRA` tier and its singleton rule are unchanged). No schema change: the self-FK `parent_organization_pk` is type-agnostic. See `docs/00_Project_Governance/GDR/GDR-008_Sakha_Asana_Is_a_Sakha_for_All_Organizational_Purposes.md`.

---

## 1. Purpose

This document defines the API contract for the Tier 2 Organization read-only API.
All endpoints are GET-only. No authentication (*at v0.8.0 — see the Tier 5 note below*).
`nss_db_backend` connects with SELECT-only privileges.

The Organization API exposes the institutional hierarchy of Nilachala Saraswata
Sangha — from the apex Kendra through Anchalika/Zilla, Sakha, and Patha Chakra
levels — along with reference data (organization types, lifecycle statuses) and
a recursive hierarchy endpoint for tree navigation.

Write operations (POST/PATCH/DELETE) are deferred to Tier 5 when authenticated
administration and authorization exist.

> **Tier 5 update (v0.11.0):**
> this router now has **8** endpoints, all gated by `require_permission("ORGANIZATION_VIEW")`
> (401 without a JWT, 403 without the permission). The 8th is
> `GET /organizations/{organization_pk}/stats` — whole-subtree `member_count`, `family_count`,
> `sakha_sanghas`, `mahila_sanghas`, `renewals_due` for the requested org itself (same FAM-036
> majority-rule counting as `/children-stats`), 403 if the org lies outside the caller's admin
> scope (ADMIN-BR-076); `OrgStatsResponse`, covered by
> `tests/security/test_organization_stats_security.py`. `/organizations` is backed by a shared
> `fetch_organizations()` that `api/routers/registration.py` reuses for the public Sakha
> dropdown. Organization **writes** live in `api/routers/admin.py` (`POST`/`PATCH
> /api/v1/admin/organizations...`, scope-gated), not here; ORG-BR-099 was narrowed so
> Anchalika/Zilla/Patha Chakra may carry country/state/district (still no premises address).
> The "7 endpoints" counts below predate `/stats`.
---

## 2. Conventions

### From Tier 0 (Carried Forward)

- **Prefix:** `/api/v1/organization`
- **Tag:** `organization`
- **Router:** `api/routers/organization.py`
- **Schemas:** `api/schemas/organization.py`
- **DB access:** `conn = Depends(get_connection)` with raw psycopg2
- **Response models:** Pydantic v2 `BaseModel` — no `ConfigDict(from_attributes=True)`
  (raw psycopg2 returns dictionaries, not ORM objects)
- **Audit columns excluded:** `created_at`, `updated_at`, `deleted_at` are never
  returned in API responses
- **Active-only by default:** All list endpoints filter `WHERE is_active = TRUE`
- **UUID path parameters:** Validated by FastAPI/Pydantic (422 on malformed UUID)
- **404 on missing:** `HTTPException(status_code=404)` when a PK lookup yields no row

### New for Tier 2

- **Shared SQL fragment:** `_ORG_SELECT` centralises the 34-column SELECT with
  8 JOINs (2 INNER + 6 LEFT) to avoid duplication across 3 endpoints
- **Combinable filters:** `type_code` and `status_code` query parameters are
  independently combinable (`if`/`if`, not `if`/`elif`)
- **Parent existence guard:** The children endpoint verifies the parent exists
  before querying, preventing `200 []` for non-existent parents
- **Recursive CTE:** The hierarchy endpoint uses a leaner 10-column query
  (no address, contact, geographic fields) for tree structure only
- **Two-field pattern for NSS-level vs org-specific:** `website_url`,
  `youtube_channel_url`, and `email` are NOT NULL DEFAULT (NSS-level,
  always present); `org_website_url`, `org_youtube_channel_url`, and
  `org_email` are nullable (org-specific)

- **Shared helpers:** `api/helpers.py` provides `rows_to_models`, `row_to_model`,
  `DEFAULT_LIMIT` (100), `MAX_LIMIT` (500) — shared across all routers
- **Pagination:** List and hierarchy endpoints support `limit` (1–500, default 100)
  and `offset` (≥0, default 0). FastAPI `Query(ge=1, le=MAX_LIMIT)` enforces bounds
  (422 on violation)
- **CTE depth guard:** Hierarchy endpoint caps recursion at depth 10
  (`AND t.depth < 10`) as defence-in-depth against circular parent references

### Endpoint Classification

| Class                          | Endpoints                                       | Consumer               |
|--------------------------------|-------------------------------------------------|------------------------|
| Reference data                 | types, statuses                                 | Dropdowns / filters    |
| Core organization data         | organizations (list, detail, children)           | Application / frontend |
| Aggregate stats                | children-stats                                   | Org admin sidebar (drill-down counts) |
| Navigation / tree              | hierarchy                                        | Tree view UI           |

---

## 3. Endpoint Catalogue

### 3.1 Reference Data

#### 3.1.1 List Organization Types

```
GET /api/v1/organization/types
```

Returns all active organization types from Foundation's shared `nss.master_data`
table, filtered to category `ORGANIZATION_TYPE` (JOINed via `nss.master_category`).

**Query Parameters:** None

**Response:** `200 OK`

```json
[
  {
    "organization_type_pk": "uuid",
    "organization_type_code": "KENDRA",
    "organization_type_name": "Kendra Sangha",
    "description": "...",
    "sort_order": 1,
    "is_active": true
  }
]
```

**Tier 2 state:** 10 frozen types matching the NSS Bye-Law hierarchy
(Kendra, Nilachala Kutira, Smruti Mandira, Anchalika Sangha, Zilla Sangha,
Sakha Sangha, Sakha Asana, Paribarik Asana, Paribarik Sangha, Patha Chakra).

**SQL Pattern:**

```sql
SELECT md.master_data_pk  AS organization_type_pk,
       md.value_code      AS organization_type_code,
       md.value_name      AS organization_type_name,
       md.description,
       md.display_order   AS sort_order,
       md.is_active
FROM   nss.master_data md
JOIN   nss.master_category mc
       ON mc.master_category_pk = md.master_category_pk
WHERE  mc.category_code = 'ORGANIZATION_TYPE'
  AND  md.is_active = TRUE
ORDER BY md.display_order
```

---

#### 3.1.2 List Statuses

```
GET /api/v1/organization/statuses
```

Returns all active lifecycle statuses from Foundation's shared `nss.master_data`
table, filtered to the unified ERP-wide category `STATUS` (JOINed via
`nss.master_category`). This is the same `STATUS` category shared by other
modules (memberships, governance, etc.) — Organization does not own a
dedicated status list.

**Query Parameters:** None

**Response:** `200 OK`

```json
[
  {
    "status_pk": "uuid",
    "status_code": "ACTIVE",
    "status_name": "Active",
    "description": "...",
    "sort_order": 3,
    "is_active": true
  }
]
```

**Tier 2 state:** as of Tier 4, `/statuses` returns only the subset of the unified `STATUS`
category applicable to Organization (via the new `master_data.applicable_modules TEXT[]`
column, checked with `'ORGANIZATION' = ANY(applicable_modules)` or `applicable_modules IS
NULL`) — **7 statuses**: Proposed, Approved, Active, Inactive, Suspended, Dissolved, Archived.
The unified `STATUS` category itself now holds 16 values total (13 original + `RENEWAL_PENDING`/
`ON_HOLD`/`DISCIPLINARY_REVIEW`, added for Membership) — Organization no longer sees the
Membership-only ones (Lapsed, Transferred, Resigned, Expelled, Deceased, Expired, and the 3 new
Membership statuses). The test gap formerly noted here is closed: `tests/api/test_organization.py`
now asserts organization-scoped statuses (`test_list_includes_org_statuses`).

**SQL Pattern:**

```sql
SELECT md.master_data_pk  AS status_pk,
       md.value_code      AS status_code,
       md.value_name      AS status_name,
       md.description,
       md.display_order   AS sort_order,
       md.is_active
FROM   nss.master_data md
JOIN   nss.master_category mc
       ON mc.master_category_pk = md.master_category_pk
WHERE  mc.category_code = 'STATUS'
  AND  md.is_active = TRUE
  AND  ('ORGANIZATION' = ANY(md.applicable_modules) OR md.applicable_modules IS NULL)
ORDER BY md.display_order
```

---

### 3.2 Core Organization Data

All three endpoints below use the shared `_ORG_SELECT` SQL fragment (36 columns,
8 JOINs) to ensure consistent column ordering and avoid duplication.

#### 3.2.1 List Organizations

```
GET /api/v1/organization/organizations
```

Returns all active organizations with resolved type, status, parent, contact,
online presence, and geographic context.

**Query Parameters:**

| Param         | Type   | Required | Default | Description                          |
|---------------|--------|----------|---------|--------------------------------------|
| `type_code`   | string | No       | —       | Filter by organization type code     |
| `status_code` | string | No       | —       | Filter by organization status code   |
| `limit`       | int    | No       | 100     | Max rows (1–500)                     |
| `offset`      | int    | No       | 0       | Rows to skip (≥0)                    |

Both filters are independently combinable. A non-matching filter returns `[]`,
not an error. `limit` and `offset` are validated by FastAPI — `limit=0` or
`limit=501` returns 422.

**Response:** `200 OK`

```json
[
  {
    "organization_pk": "uuid",
    "organization_id": null,
    "organization_name": "Nilachala Saraswata Sangha",
    "organization_code": "KEN",

    "organization_type_pk": "uuid",
    "organization_type_code": "KENDRA",
    "organization_type_name": "Kendra Sangha",

    "status_pk": "uuid",
    "status_code": "ACTIVE",
    "status_name": "Active",

    "parent_organization_pk": null,
    "parent_organization_name": null,

    "address_line_1": "Satsikshya Mandir, A/4, Unit-9",
    "address_line_2": "Bhubaneswar",

    "phone_number": "+91-674-2390055",
    "mobile_number": "+91-9238106823",
    "email": "info@nsspuri.org",
    "org_email": null,

    "website_url": "https://www.nsspuri.org",
    "org_website_url": null,
    "youtube_channel_url": "https://www.youtube.com/@NilachalaSaraswataSangha",
    "org_youtube_channel_url": null,

    "district_pk": null,
    "district_name": null,
    "state_pk": null,
    "state_name": null,
    "country_pk": "uuid",
    "country_name": "India",
    "city_village_pk": null,
    "city_village_name": null,
    "postal_code_pk": "uuid",
    "postal_code": "751022",

    "latitude": null,
    "longitude": null,

    "is_active": true
  }
]
```

**Tier 2 state:** 3 seeded organizations (Kendra, Nilachala Kutira,
Smruti Mandira) — all roots, no children.

**SQL Pattern (shared `_ORG_SELECT`):**

```sql
SELECT o.organization_pk,
       o.organization_id,
       o.organization_name,
       o.organization_code,
       ot.master_data_pk   AS organization_type_pk,
       ot.value_code       AS organization_type_code,
       ot.value_name       AS organization_type_name,
       os.master_data_pk   AS status_pk,
       os.value_code       AS status_code,
       os.value_name       AS status_name,
       o.parent_organization_pk,
       p.organization_name AS parent_organization_name,
       o.address_line_1,
       o.address_line_2,
       o.phone_number,
       o.mobile_number,
       o.email,
       o.org_email,
       o.website_url,
       o.org_website_url,
       o.youtube_channel_url,
       o.org_youtube_channel_url,
       o.district_pk,
       d.district_name,
       o.state_pk,
       s.state_name,
       o.country_pk,
       c.country_name,
       o.city_village_pk,
       cv.city_village_name,
       o.postal_code_pk,
       pc.postal_code,
       o.latitude,
       o.longitude,
       o.is_active
FROM   nss.organization o
JOIN   nss.master_data ot
       ON ot.master_data_pk = o.organization_type_master_data_pk
JOIN   nss.master_data os
       ON os.master_data_pk = o.status_master_data_pk
LEFT JOIN nss.organization p
       ON p.organization_pk = o.parent_organization_pk
LEFT JOIN nss.district d
       ON d.district_pk = o.district_pk
LEFT JOIN nss.state s
       ON s.state_pk = o.state_pk
LEFT JOIN nss.country c
       ON c.country_pk = o.country_pk
LEFT JOIN nss.city_village cv
       ON cv.city_village_pk = o.city_village_pk
LEFT JOIN nss.postal_code pc
       ON pc.postal_code_pk = o.postal_code_pk
WHERE  o.is_active = TRUE
ORDER BY ot.display_order, o.organization_name
LIMIT %s OFFSET %s
```

When `type_code` is provided, add: `AND ot.value_code = %s`
When `status_code` is provided, add: `AND os.value_code = %s`

---

#### 3.2.2 Get Organization by PK

```
GET /api/v1/organization/organizations/{organization_pk}
```

Returns a single organization with full resolved context. 404 if not found
or inactive.

**Path Parameters:**

| Param              | Type | Required | Description              |
|--------------------|------|----------|--------------------------|
| `organization_pk`  | UUID | Yes      | Organization primary key |

**Response:** `200 OK` — single `OrganizationResponse`

**Error Responses:**

| Status | When                                |
|--------|-------------------------------------|
| 404    | PK not found or inactive            |
| 422    | Malformed UUID                      |

**SQL Pattern:** `_ORG_SELECT` + `WHERE o.organization_pk = %s AND o.is_active = TRUE`

---

#### 3.2.3 List Organization Children

```
GET /api/v1/organization/organizations/{organization_pk}/children
```

Returns direct children of a given organization. 404 if the parent
does not exist.

**Path Parameters:**

| Param              | Type | Required | Description                    |
|--------------------|------|----------|--------------------------------|
| `organization_pk`  | UUID | Yes      | Parent organization primary key |

**Response:** `200 OK` — list of `OrganizationResponse`

**Error Responses:**

| Status | When                                     |
|--------|------------------------------------------|
| 404    | Parent `organization_pk` not found       |
| 422    | Malformed UUID                           |

**Design note:** The two-step pattern (existence check + children query)
prevents a non-existent parent from silently returning `200 []`, which
would be indistinguishable from "parent exists but has no children."

**Tier 2 state:** All 3 seeded organizations are roots — this endpoint
returns `[]` for all valid parents. Children will appear when Anchalika,
Zilla, Sakha, and Patha Chakra organizations are created.

**SQL Pattern:**

```sql
-- Step 1: Verify parent exists
SELECT 1 FROM nss.organization
WHERE  organization_pk = %s AND is_active = TRUE

-- Step 2: Fetch children
_ORG_SELECT
WHERE  o.parent_organization_pk = %s AND o.is_active = TRUE
ORDER BY ot.display_order, o.organization_name
```

---

#### 3.2.4 List Children Stats (Tier 4)

```
GET /api/v1/organization/organizations/{organization_pk}/children-stats
```

For each **direct** child of the given organization, recursively walks every descendant
Sakha (`SAKHA_SANGHA`-typed organization, at any depth) and returns aggregate
family/member/person counts rolled up to that direct child. New on top of Tier 4 Family +
Membership. The router docstring states this is "used by the org admin sidebar to display
inline counts on each drill-down card". **Consumer (updated):** the original
`organization.html` page never called it, and `admin.html`'s Organization Hierarchy tab still
doesn't; the real consumer is the org family browser in `frontend/dashboard.html`
(`frontend/assets/js/dashboard.js::_fetchOrgChildrenStats()`).

**Path Parameters:**

| Param              | Type | Required | Description                    |
|--------------------|------|----------|--------------------------------|
| `organization_pk`  | UUID | Yes      | Parent organization primary key |

**Response:** `200 OK` — list of `OrgChildStatsResponse`

```json
[
  {
    "organization_pk": "uuid",
    "organization_name": "Puri Anchalika Sangha",
    "organization_code": "PUR-ANC",
    "organization_type_code": "ANCHALIKA_SANGHA",
    "family_count": 12,
    "member_count": 18,
    "person_count": 41
  }
]
```

**Error Responses:**

| Status | When                                |
|--------|-------------------------------------|
| 404    | Parent `organization_pk` not found or inactive |
| 422    | Malformed UUID                      |

**Design note — dynamic Sakha via FAM-036:** `family_count`/`member_count`/`person_count`
are **not** simple joins against each family's stored `sakha_organization_pk`. A family's
*effective* Sakha is computed the same way Family's own
`GET /api/v1/family/families/{pk}/sakha-alignment` endpoint computes it (FAM-036 — see
`docs/03_Solution/modules/family/04_family_business_rules.md`): the Sakha that holds a
majority of the family's members' active Sangha Sevi affiliations, falling back to the
family's stored `sakha_organization_pk` when no member has an active affiliation. This means
a family whose members have mostly re-affiliated to a different Sakha than the one it is
registered under counts toward the *new* Sakha's parent chain here, not the registration
Sakha's. **`family_count`** counts distinct families whose effective Sakha falls under the
child (rolled up through any number of intermediate levels). **`member_count`** counts
distinct Sangha Sevis with an active affiliation (`effective_to IS NULL`) directly to one of
the descendant Sakhas — independent of family majority, so a member whose own affiliation
disagrees with their family's majority Sakha is counted under their own Sakha, not their
family's. **`person_count`** counts distinct current family members (`is_current = TRUE`)
across every family whose effective Sakha falls under the child, whether or not that person
individually holds a membership — so `member_count <= person_count` always holds. For a
non-Sakha organization type with no Sakha descendants at all (e.g. a leaf Patha Chakra), all
three counts are `0`, not an error.

**Maintainability note:** the FAM-036 majority-rule SQL (a `family_majority` CTE ranking each
family's Sakha affiliations by count via `ROW_NUMBER() OVER (PARTITION BY family_group_pk
ORDER BY COUNT(*) DESC)`) is implemented **twice** — once here in
`_CHILDREN_STATS_SQL`, and independently again in `api/routers/family.py`'s `_FAMILY_SELECT` —
rather than being factored into one shared SQL fragment. Not fixed as part of adding this
endpoint; flagged here for future consolidation.

**Tier 4 state:** counts depend on the Tier 4 Family + Membership verification seed data
(family/member/person counts vary by which children/Sakhas are seeded under the queried
parent); a leaf Sakha (no children of its own) always returns `[]`.

**SQL Pattern:** a `WITH RECURSIVE` CTE (`org_tree`, anchored on the requested parent's direct
children, each row carrying forward a `root_child_pk` column so descendants at any depth still
know which direct child they roll up to) feeding into `sakha_pks` (Sakha-typed descendants
only), `family_majority`/`family_effective` (the FAM-036 computation described above),
and three `LEFT JOIN`ed aggregate CTEs (`family_counts`, `member_counts`, `person_counts`,
each `COALESCE`d to `0`). See `api/routers/organization.py`'s `_CHILDREN_STATS_SQL` and
`docs/03_Solution/code_explanations/API_CODE_EXPLANATIONS.md` §2.9 for the full query and a
line-by-line walkthrough of each CTE.

---

### 3.3 Navigation

#### 3.3.1 Organization Hierarchy

```
GET /api/v1/organization/hierarchy
```

Returns the full organizational hierarchy as a flat list with depth.
Uses a recursive CTE starting from root nodes (`parent = NULL`).
Depth is capped at 10 levels as a defence-in-depth guard against circular
parent references.

**Query Parameters:**

| Param    | Type | Required | Default | Description          |
|----------|------|----------|---------|----------------------|
| `limit`  | int  | No       | 100     | Max rows (1–500)     |
| `offset` | int  | No       | 0       | Rows to skip (≥0)    |

**Response:** `200 OK`

```json
[
  {
    "organization_pk": "uuid",
    "organization_name": "Nilachala Saraswata Sangha",
    "organization_code": "KEN",
    "organization_type_code": "KENDRA",
    "organization_type_name": "Kendra Sangha",
    "status_code": "ACTIVE",
    "status_name": "Active",
    "parent_organization_pk": null,
    "depth": 0,
    "is_active": true
  }
]
```

**Design note:** Uses a leaner 10-column query (vs 36 in `_ORG_SELECT`) —
no address, contact, online-presence, or geographic fields. The hierarchy
view shows only organizational structure (name, type, status, depth).
The UI reconstructs the tree using `depth` for indentation; the response
is deliberately flat, not nested JSON.

**Tier 2 state:** 3 root nodes at depth 0. When child organizations are
created, deeper levels will appear (Kendra → Anchalika → Sakha → Patha Chakra
= depth 0 → 1 → 2 → 3).

**SQL Pattern:**

```sql
WITH RECURSIVE org_tree AS (
    -- Anchor: root nodes (no parent)
    SELECT o.organization_pk, o.organization_name,
           o.organization_code,
           ot.value_code  AS organization_type_code,
           ot.value_name  AS organization_type_name,
           os.value_code  AS status_code,
           os.value_name  AS status_name,
           o.parent_organization_pk,
           0 AS depth, o.is_active
    FROM   nss.organization o
    JOIN   nss.master_data ot
           ON ot.master_data_pk = o.organization_type_master_data_pk
    JOIN   nss.master_data os
           ON os.master_data_pk = o.status_master_data_pk
    WHERE  o.parent_organization_pk IS NULL
      AND  o.is_active = TRUE

    UNION ALL

    -- Recursive: children
    SELECT o.organization_pk, o.organization_name,
           o.organization_code,
           ot.value_code  AS organization_type_code,
           ot.value_name  AS organization_type_name,
           os.value_code  AS status_code,
           os.value_name  AS status_name,
           o.parent_organization_pk,
           t.depth + 1, o.is_active
    FROM   nss.organization o
    JOIN   nss.master_data ot
           ON ot.master_data_pk = o.organization_type_master_data_pk
    JOIN   nss.master_data os
           ON os.master_data_pk = o.status_master_data_pk
    JOIN   org_tree t
           ON t.organization_pk = o.parent_organization_pk
    WHERE  o.is_active = TRUE
      AND  t.depth < 10
)
SELECT * FROM org_tree
ORDER BY depth, organization_name
LIMIT %s OFFSET %s
```

---

## 4. Response Schema Summary

### Pydantic Models (api/schemas/organization.py)

| Model                              | Endpoint(s)                          | Field Count |
|------------------------------------|--------------------------------------|-------------|
| `OrganizationTypeResponse`         | types                                | 6           |
| `StatusResponse`                   | statuses                             | 6           |
| `OrganizationResponse`             | organizations, detail, children      | 36          |
| `OrgChildStatsResponse`            | children-stats                       | 7           |
| `OrganizationHierarchyNodeResponse`| hierarchy                            | 10          |

### OrganizationResponse — 34 Fields by Group

| Group              | Fields                                                                                          |
|--------------------|-------------------------------------------------------------------------------------------------|
| Core (4)           | organization_pk, organization_id, organization_name, organization_code                          |
| Classification (3) | organization_type_pk, organization_type_code, organization_type_name                            |
| Lifecycle (3)      | status_pk, status_code, status_name                                                              |
| Hierarchy (2)      | parent_organization_pk, parent_organization_name                                                |
| Address (2)        | address_line_1, address_line_2                                                                  |
| Contact (4)        | phone_number, mobile_number, email, org_email                                                   |
| Online Presence (4)| website_url, org_website_url, youtube_channel_url, org_youtube_channel_url                       |
| Geographic (10)    | district_pk, district_name, state_pk, state_name, country_pk, country_name, city_village_pk, city_village_name, postal_code_pk, postal_code |
| Coordinates (2)    | latitude, longitude                                                                             |
| Status (1)         | is_active                                                                                       |

### Two-Field Pattern (NSS-Level vs Org-Specific)

| NSS-Level (NOT NULL DEFAULT)    | Org-Specific (nullable)        | Purpose                    |
|---------------------------------|--------------------------------|----------------------------|
| `email`                         | `org_email`                    | NSS email vs org's own     |
| `website_url`                   | `org_website_url`              | NSS website vs org's own   |
| `youtube_channel_url`           | `org_youtube_channel_url`      | NSS YouTube vs org's own   |

Every organization inherits the NSS website and YouTube channel via DEFAULT.
If an organization (e.g., a Sakha) has its own website or YouTube channel,
those go in the `org_*` columns. The UI displays both when present.

### Fields Deliberately Excluded

| Field                          | Reason                                      |
|--------------------------------|---------------------------------------------|
| `created_at`                   | System audit — not API-facing (Tier 0 rule) |
| `updated_at`                   | System audit — not API-facing               |
| `deleted_at`                   | System audit — not API-facing               |

---

## 5. Endpoint Count Summary

| Group              | Endpoints | Tables Covered                                            |
|--------------------|-----------|-----------------------------------------------------------|
| Reference Data     | 2         | master_data (categories ORGANIZATION_TYPE, STATUS)         |
| Core Organizations | 3         | organization (list, detail, children)                     |
| Aggregate Stats    | 1         | organization + family_group/family_relationship/sangha_sevi/membership_sakha_affiliation (children-stats, dynamic FAM-036 rollup) |
| Navigation         | 1         | organization (recursive CTE)                              |
| Subtree Stats (Tier 5) | 1     | organization + family/membership tables (`/stats`)        |
| **Total**          | **8**     | **1 table (`organization`) + 4 Family/Membership tables (read-only, for children-stats) + 2 shared Foundation master_data categories** |

---

## 6. Error Responses

Carried forward from Tier 0:

| Status | When                                      | Body                                     |
|--------|-------------------------------------------|------------------------------------------|
| 200    | Success                                   | Response model (list or single)          |
| 404    | PK lookup — not found or inactive         | `{"detail": "Organization not found"}`   |
| 404    | Parent PK — not found or inactive         | `{"detail": "Parent organization not found"}` |
| 422    | Malformed UUID or invalid query parameter | FastAPI validation error                 |
| 422    | `limit=0`, `limit=501`, `offset=-1`      | FastAPI validation error (ge/le bounds)  |

---

## 7. Implementation File Map

```
api/
  helpers.py                        <- Shared cursor→Pydantic helpers + pagination constants
  routers/
    organization.py             <- 8 endpoint handlers + _ORG_SELECT + _CHILDREN_STATS_SQL + _ORG_STATS_SQL
    family.py                   <- splices the same shared FAMILY_MAJORITY_CTE_SQL (api/helpers.py)
  schemas/
    organization.py             <- 5 Pydantic response models (incl. OrgChildStatsResponse)
database/
  ddl/02_organization/
    03_organization.sql              (FKs → nss.master_data)
  seed/02_organization/
    03_organization.sql              (3 organizations)
  ddl/01_foundation/
    02_master_category.sql           (includes ORGANIZATION_TYPE, STATUS)
    08_master_data.sql                (type/status values live here)
  seed/01_foundation/
    01_master_category.sql           (ORGANIZATION_TYPE, STATUS categories)
    02_master_data.sql               (10 ORGANIZATION_TYPE values, 13 STATUS values)
tests/
  api/test_organization.py      <- Integration tests, incl. TestChildrenStats
  security/test_organization_stats_security.py <- /stats gating
frontend/
  admin.html                    <- Organization UI: Organizations + Organization Hierarchy
                                   tabs (replaces the retired organization.html);
  dashboard.html                <- org family browser consuming /children-stats
docs/
  03_Solution/code_explanations/
      API_CODE_EXPLANATIONS.md        <- Code walkthrough (SS2.9-2.10)
      TIER2_SECURITY_AUDIT.md         <- Security audit (15 checks)
      TESTING_CODE_EXPLANATIONS.md    <- Test walkthrough (SS2.5)
```

---

## 8. Seed Data Summary

| Organization                        | Code | Type           | Contact                                       | Online Presence                |
|-------------------------------------|------|----------------|-----------------------------------------------|--------------------------------|
| Nilachala Saraswata Sangha          | KEN  | Kendra         | Ph: +91-674-2390055, Mob: +91-9238106823      | NSS website + YouTube (DEFAULT)|
| Nilachala Kutira                    | NKT  | Nilachala Kutira | —                                            | NSS website + YouTube (DEFAULT)|
| Sri Shri Nigamananda Smruti Mandir  | SMR  | Smruti Mandira | Ph: +91-6752-230631, Email: info@nsspuri.org  | NSS website + YouTube (DEFAULT)|

All 3 organizations are roots (`parent_organization_pk = NULL`).
All 3 inherit `website_url` and `youtube_channel_url` from column DEFAULTs.

---

## 9. Future (Tier 5+)

When Authentication + Administration arrives:

```
Authenticated user
       |
ERP role + permission + scope
       |
POST   /api/v1/organization/organizations          (create)
PATCH  /api/v1/organization/organizations/{pk}      (update)
DELETE /api/v1/organization/organizations/{pk}      (soft-delete)
```

Write operations will include:
- Contact field validation (email format, phone format)
- `org_website_url` and `org_youtube_channel_url` population
- Organization lifecycle transitions (e.g., Proposed -> Active)
- Child organization creation under parent hierarchy

The DB role (`nss_db_backend`) will be granted narrowly scoped write privileges
at that time — not before. A separate `nss_db_writer` role is not created until
an authenticated write requirement exists.

---

## 10. Non-Breaking Extension Points

These can be added later without changing existing contracts:

| Extension          | Mechanism                                     |
|--------------------|-----------------------------------------------|
| Text search        | Add `?search=...` using existing GIN index on `organization_name` |
| Include inactive   | Add `?include_inactive=true` (auth-gated)     |

**Already implemented (formerly listed here):**

| Feature            | Implementation                                |
|--------------------|-----------------------------------------------|
| Pagination         | `limit`/`offset` on list + hierarchy (default 100, max 500) |
| Recursive depth    | `AND t.depth < 10` guard in hierarchy CTE     |

**Deliberately excluded from this list:**

| Capability               | Why                                                     |
|--------------------------|---------------------------------------------------------|
| Include inactive records | Authorization concern — admin-only when auth exists     |
| Nested JSON hierarchy    | Flat + depth is the chosen pattern; UI reconstructs tree|
| President/governance     | Deferred to Tier 3 Membership (role-assignment model)   |
