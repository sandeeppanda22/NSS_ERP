# Bootstrap API Contract — Tier 0 Read-Only

| Field       | Value                                          |
|-------------|------------------------------------------------|
| Document    | BOOTSTRAP_API_CONTRACT                         |
| Version     | 1.1                                            |
| Tier        | 0 — Bootstrap (RBAC)                           |
| Authority   | SOL-ARCH-010, SOL-RBAC-001                     |
| Status      | DRAFT                                          |

---

## 1. Purpose

This document defines the API contract for the Tier 0 Bootstrap read-only API.
All endpoints are GET-only. No authentication. `nss_db_backend` connects with
SELECT-only privileges.

> **Tier 5 update (v0.11.0):**
> these 4 endpoints are still the only routes in the whole API that need no JWT. What changed is
> the *data*: `role_master` now seeds **9** roles, and `permission_master`/`role_permission` are
> **seeded** (`database/seed/00_bootstrap/01_permission_master.sql`, `03_role_permission.sql`),
> so `/permissions` and `/roles/{pk}/permissions` return real rows. The "8 roles" / "empty by
> design" / "always returns empty list" statements in §5-§7 below describe the original Tier 0
> state and are superseded. Write/management of roles and permissions lives in the
> Administration router (`/api/v1/admin/users/{pk}/roles`), not here.
>
> **2026-10-09 update:** `role_master` now seeds **10** roles — `NSS_ERP_ADVISORY_BOARD_ADMIN`
> (scope `ADVISORY_BOARD`) was added as part of the §63 composite auto-grant rule. The "9 roles"
> statement above describes the Tier 5 state at that time and is now superseded; see §4 below.
> `permission_master` now seeds **23** permissions — Tier 6 added `GOVERNANCE_VIEW` and
> `GOVERNANCE_MANAGE` (module `GOVERNANCE`; `GOVERNANCE_VIEW` to the org-scoped admins and
> `NSS_ERP_AUDITOR`, `GOVERNANCE_MANAGE` to `NSS_ERP_ADMIN`, `NSS_ERP_KENDRA_ADMIN` and
> `NSS_ERP_SAKHA_ADMIN`), and the new role's `role_class` is `ORGANIZATIONAL`.

Bootstrap exposes the RBAC foundation: roles, permissions, and their mappings.
These are infrastructure tables — the API serves verification and future
administration UI, not end-user consumption.

---

## 2. Conventions

- **Prefix:** `/api/v1/bootstrap`
- **Tag:** `bootstrap`
- **Router:** `api/routers/bootstrap.py`
- **Schemas:** `api/schemas/bootstrap.py`
- **DB access:** `conn = Depends(get_connection)` with raw psycopg2
- **Response models:** Pydantic v2 `BaseModel` — no `ConfigDict(from_attributes=True)`
  (raw psycopg2 returns dictionaries, not ORM objects)
- **Audit columns excluded:** `created_at`, `updated_at`, `deleted_at` are never
  returned in API responses
- **Active-only by default:** All list endpoints filter `WHERE is_active = TRUE`
- **UUID path parameters:** Validated by FastAPI/Pydantic (422 on malformed UUID)
- **404 on missing:** `HTTPException(status_code=404)` when a PK lookup yields no row

---

## 3. Endpoint Catalogue

### 3.1 Health Check

#### 3.1.1 Health

```
GET /api/v1/bootstrap/health
```

Liveness/readiness probe. Returns database connectivity status. Never exposes
connection details, credentials, or error messages.

**Query Parameters:** None

**Response:** `200 OK`

```json
{
  "status": "ok",
  "database": "connected"
}
```

When the database is unreachable:

```json
{
  "status": "degraded",
  "database": "unreachable"
}
```

**Design note:** `check_connection()` is a separate function from `get_connection()`
— it catches all exceptions internally and returns a boolean. No database error
details ever reach the response.

---

### 3.2 Roles

#### 3.2.1 List Roles

```
GET /api/v1/bootstrap/roles
```

Returns all active roles from `nss.role_master`.

**Query Parameters:** None

**Response:** `200 OK`

```json
[
  {
    "role_master_pk": "uuid",
    "role_code": "PRESIDENT",
    "role_name": "President",
    "role_class": "GOVERNANCE",
    "scope_level": "KENDRA",
    "description": "...",
    "display_order": 1,
    "is_active": true
  }
]
```

**Tier 0 state:** 8 frozen roles at v0.6.0; 9 in Tier 5; **10 since 2026-10-09** (see the update note in §1).

**SQL Pattern:**

```sql
SELECT role_master_pk, role_code, role_name,
       role_class, scope_level, description,
       display_order, is_active
FROM   nss.role_master
WHERE  is_active = TRUE
ORDER BY display_order
```

---

### 3.3 Permissions

#### 3.3.1 List Permissions

```
GET /api/v1/bootstrap/permissions
```

Returns all active permissions from `nss.permission_master`.

**Query Parameters:** None

**Response:** `200 OK`

```json
[
  {
    "permission_master_pk": "uuid",
    "permission_code": "ORG_VIEW",
    "permission_name": "View Organizations",
    "module_code": "ORGANIZATION",
    "description": "...",
    "display_order": 1,
    "is_active": true
  }
]
```

**Tier 0 state:** Empty by design at v0.6.0; **populated in Tier 5** (21 permissions); **23 since Tier 6** (`GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`; see the update note in §1).

**SQL Pattern:**

```sql
SELECT permission_master_pk, permission_code, permission_name,
       module_code, description, display_order, is_active
FROM   nss.permission_master
WHERE  is_active = TRUE
ORDER BY module_code, display_order
```

---

#### 3.3.2 List Role Permissions

```
GET /api/v1/bootstrap/roles/{role_pk}/permissions
```

Returns permissions assigned to a specific role via `nss.role_permission`
junction table. 404 if the role does not exist.

**Path Parameters:**

| Param     | Type | Required | Description        |
|-----------|------|----------|--------------------|
| `role_pk` | UUID | Yes      | Role primary key   |

**Response:** `200 OK` — list of `PermissionResponse`

**Error Responses:**

| Status | When                           |
|--------|--------------------------------|
| 404    | `role_pk` not found or inactive |
| 422    | Malformed UUID                 |

**Tier 0 state:** Returned an empty list at v0.6.0; **returns real mappings in Tier 5** for roles that have them. The endpoint exists to establish the contract and verify the
junction-table query path.

**SQL Pattern:**

```sql
-- Step 1: Verify role exists
SELECT 1 FROM nss.role_master
WHERE  role_master_pk = %s AND is_active = TRUE

-- Step 2: Fetch permissions via junction
SELECT pm.permission_master_pk, pm.permission_code,
       pm.permission_name, pm.module_code,
       pm.description, pm.display_order, pm.is_active
FROM   nss.role_permission rp
JOIN   nss.permission_master pm
       ON pm.permission_master_pk = rp.permission_master_pk
WHERE  rp.role_master_pk = %s
  AND  rp.is_active = TRUE
  AND  pm.is_active = TRUE
ORDER BY pm.module_code, pm.display_order
```

**Design note:** The two-step pattern (existence check + data fetch) prevents
a non-existent role from silently returning `200 []`, which would be
indistinguishable from "role exists but has no permissions."

---

## 4. Response Schema Summary

### Pydantic Models (api/schemas/bootstrap.py)

| Model                | Endpoint(s)                              | Fields                                                                                        |
|----------------------|------------------------------------------|-----------------------------------------------------------------------------------------------|
| `HealthResponse`     | health                                   | status, database                                                                              |
| `RoleResponse`       | roles                                    | role_master_pk, role_code, role_name, role_class, scope_level, description, display_order, is_active |
| `PermissionResponse` | permissions, roles/{pk}/permissions      | permission_master_pk, permission_code, permission_name, module_code, description, display_order, is_active |

### Fields Deliberately Excluded

| Field                          | Reason                                      |
|--------------------------------|---------------------------------------------|
| `created_at`                   | System audit — not API-facing               |
| `updated_at`                   | System audit — not API-facing               |
| `deleted_at`                   | System audit — not API-facing               |
| `created_by_sangha_sevi_pk`    | FK target doesn't exist yet                 |

---

## 5. Endpoint Count Summary

| Group              | Endpoints | Tables Covered                                           |
|--------------------|-----------|----------------------------------------------------------|
| Health             | 1         | Database connectivity check (no table query)             |
| Roles              | 1         | role_master                                              |
| Permissions        | 2         | permission_master, role_permission (junction)            |
| **Total**          | **4**     | **3 tables exposed**                                     |

---

## 6. Error Responses

| Status | When                                      | Body                                |
|--------|-------------------------------------------|-------------------------------------|
| 200    | Success                                   | Response model (list or single)     |
| 404    | Role PK lookup — not found or inactive    | `{"detail": "Role not found"}`      |
| 422    | Malformed UUID path parameter             | FastAPI validation error            |

---

## 7. Implementation File Map

```
api/
  routers/
    bootstrap.py               <- 4 endpoint handlers
  schemas/
    bootstrap.py               <- 3 Pydantic response models
tests/
  test_bootstrap.py            <- Integration tests
frontend/
  admin.html                   <- Bootstrap RBAC UI: System Settings tab
                                  (replaces the retired index.html)
docs/
  03_Solution/code_explanations/
      API_CODE_EXPLANATIONS.md       <- Code walkthrough
      TIER0_SECURITY_AUDIT.md        <- Security audit
      TESTING_CODE_EXPLANATIONS.md   <- Test walkthrough
```

---

## 8. Future (Tier 5+)

Role assignment is implemented in the Tier 5 Administration router. Permission-catalogue
writes via this router remain unbuilt; if added they would look like:

```
Authenticated user
       |
ERP role + permission + scope
       |
POST   /api/v1/bootstrap/permissions              (create)
POST   /api/v1/bootstrap/roles/{pk}/permissions    (assign)
DELETE /api/v1/bootstrap/roles/{pk}/permissions/{pk} (revoke)
```

Write operations will be added per-endpoint as authorized use cases emerge.
The DB role (`nss_db_backend`) will be granted narrowly scoped write privileges
at that time — not before.
