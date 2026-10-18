# NSS ERP — API Contract Reference

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | API Contract Reference |
| Document ID | SOL-API-001 |
| Domain | Cross-Module |
| Repository Path | docs/03_Solution/api/API_CONTRACT.md |
| Version | 1.1.0 |
| Status | Draft |
| Authority | NSS ERP Architecture |
| Effective Date | TBD |

---

# 1. Overview

The NSS ERP exposes a REST API (FastAPI, raw `psycopg2`, no ORM) of **201 endpoints** across 15
routers. Tiers 0-4 were originally read-only and unauthenticated; **Tier 5
(released as v0.11.0)** added JWT authentication, RBAC, write endpoints, and gated almost everything:

- **Only the 4 Tier 0 `bootstrap.py` endpoints and the 12 `/api/v1/register` endpoints (public
  self-registration + its reference-data lookups) plus `POST /auth/login|refresh|forgot-password|
  reset-password` are reachable without a JWT.** Everything else needs
  `Authorization: Bearer <access token>`.
- Read endpoints connect as `nss_db_backend` (SELECT-only, `get_connection`); write endpoints
  connect as `nss_db_writer` (`get_write_connection`, SELECT + INSERT/UPDATE on every `nss` table,
  no DELETE/DDL).
- Authorization is one of three models, stated per endpoint below: a blanket
  `require_permission("X")`/`require_any_permission(...)` gate; an **ownership** check
  (the caller reaches their own record — `family.py`'s `family_relationship`/`family_admin`
  rows, or "self or permission" on Person/Membership sub-resources); or plain
  `get_current_user` (any valid JWT).
- Every `nss.*` INSERT/UPDATE/DELETE is additionally captured by a DB-level audit trigger into
  `nss.system_event_log`; `field_change_log` is readable only through `GET /api/v1/audit/change-log`.

**Tier 6 (Governance, uncommitted on `feature/tier6-governance`)** adds `governance.py` (46
endpoints, section 12c), `membership_change_request.py` (5, section 8b), `correspondence.py`
(9, section 12d) and four admin credential endpoints (the `T6` rows in section 12).

Tier 5 endpoints (sections 10-14) are summarized here only at table level — see the routers
(`api/routers/auth.py`, `admin.py`, `claim_approval.py`, `registration.py`, `audit.py`), their
module docstrings, and `docs/03_Solution/security/TIER5_SECURITY_AUDIT.md` for request/response
detail; no standalone Tier 5 contract document exists yet.

**Base URL:** `http://localhost:8001`

**API prefix:** `/api/v1/<module>`

**Content type:** `application/json`

---

# 2. Common Conventions

## 2.1 Pagination

All list endpoints **except Bootstrap's and Foundation's** (which return full, unpaginated
lists — Foundation's largest table is ~700 rows) support:

| Parameter | Type | Default | Constraint |
|---|---|---|---|
| `limit` | int | 100 | 1 ≤ limit ≤ 500 |
| `offset` | int | 0 | offset ≥ 0 |

- `limit=0` or `limit > 500` → `422 Unprocessable Entity`
- `offset=-1` → `422`
- `offset` beyond total rows → empty list `[]`, not error

**Envelope exception — Person and Membership list/search:** `GET /person/persons`,
`GET /person/search`, `GET /membership/members`, and `GET /membership/search`
do **not** return a bare array. They return `{persons|members: [...], total: N}`.
`total` is the true row count matching the filters, independent of the
`limit`/MAX_LIMIT cap on the array — the array alone cannot reveal whether more
rows exist beyond the page returned. Callers must compare `total` to
`len(persons|members)` to detect truncation. `/person/search` and
`/membership/search` additionally accept `limit`/`offset` like the list
endpoints (default 50, max 500) — previously they had a hardcoded `LIMIT 50`
with no way to page past it and no `total`.

## 2.2 Error Responses

| Status | Meaning |
|---|---|
| 200 / 201 | Success / created |
| 400 | Business-rule violation (Tier 5 write endpoints) |
| 401 | Missing, invalid or expired JWT (Tier 5) |
| 403 | Authenticated but lacks the required permission/ownership/admin scope (Tier 5) |
| 404 | Resource not found (valid UUID, no match) |
| 409 | Conflict — duplicate/unique violation (Tier 5 write endpoints) |
| 422 | Validation error (bad UUID, bad parameter) — `api/error_handlers.py` rewrites FastAPI/Pydantic and DB-integrity errors into human-readable messages |
| 429 | Rate limit exceeded |

**Sorting:** list endpoints on Person, Membership and Admin (users, claims, organizations)
accept optional `sort_by`/`sort_dir`, validated against a per-endpoint column whitelist
(`api/helpers.py`); an unknown `sort_by` returns `422`.

## 2.3 Audit Column Exclusion

No endpoint returns audit columns:

```text
created_at, updated_at, deleted_at,
created_by_sangha_sevi_pk, updated_by_sangha_sevi_pk, deleted_by_sangha_sevi_pk
```

## 2.4 Sensitive Data

- `aadhaar_encrypted` and `aadhaar_hash` are never returned.
- `aadhaar_last4` appears only in Person detail, not list/search.

## 2.5 UUID Path Parameters

All `{pk}` parameters expect a valid UUID v4. Malformed UUIDs return `422`.

---

# 3. Tier 0 — Bootstrap

**Router prefix:** `/api/v1/bootstrap`

| # | Method | Path | Description | Response Model |
|---|---|---|---|---|
| 1 | GET | `/health` | Database connectivity check | `HealthResponse` |
| 2 | GET | `/roles` | List RBAC roles | `list[RoleResponse]` |
| 3 | GET | `/permissions` | List RBAC permissions | `list[PermissionResponse]` |
| 4 | GET | `/roles/{role_pk}/permissions` | Permissions assigned to a role (404 if role not found) | `list[PermissionResponse]` |

**Auth:** none — the only fully unauthenticated router. `permission_master`/`role_permission`
are now seeded, so `/permissions` and `/roles/{pk}/permissions` return real rows.

---

# 4. Tier 1 — Foundation

**Router prefix:** `/api/v1/foundation` — 33 endpoints (see the Tier 5 write/extension rows below): reads gated by
`require_permission("FOUNDATION_VIEW")`, `nss_db_backend`), admin writes gated by
`require_permission("FOUNDATION_MANAGE")` (`nss_db_writer`, each logs via `log_audit()`), and four member `propose` endpoints gated by `get_current_user` only.
`field_change_log` is deliberately **not** exposed here (no `/foundation/change-log`).

| # | Method | Path | Filters | Description | Response Model |
|---|---|---|---|---|---|
| 5 | GET | `/categories` | — | List master categories | `list[CategoryResponse]` |
| 6 | GET | `/categories/{pk}` | — | Category detail | `CategoryResponse` |
| 7 | GET | `/master-data` | `category_code`, `category_pk` | List master data | `list[MasterDataResponse]` |
| 8 | GET | `/master-data/{pk}` | — | Master data detail | `MasterDataResponse` |
| 9 | GET | `/settings` | — | List system settings | `list[SettingResponse]` |
| 10 | GET | `/settings/{key}` | — | Setting by key | `SettingResponse` |
| 11 | GET | `/sequences` | — | List ID sequences | `list[SequenceResponse]` |
| 12 | GET | `/countries` | — | List countries | `list[CountryResponse]` |
| 13 | GET | `/countries/{pk}` | — | Country detail | `CountryResponse` |
| 14 | GET | `/states` | `country_pk` | List states | `list[StateResponse]` |
| 15 | GET | `/states/{pk}` | — | State detail | `StateResponse` |
| 16 | GET | `/districts` | `state_pk` | List districts | `list[DistrictResponse]` |
| 17 | GET | `/districts/{pk}` | — | District detail | `DistrictResponse` |
| 18 | GET | `/cities` | `district_pk` | List cities/villages | `list[CityVillageResponse]` |
| 19 | GET | `/postal-codes` | `state_pk`, `country_pk` | List postal codes | `list[PostalCodeResponse]` |
| 20 | GET | `/postal-code-mappings` | `postal_code_pk`, `city_village_pk` | List postal code mappings | `list[PostalCodeMappingResponse]` |
| 21 | GET | `/documents` | `document_type_code` | List document masters | `list[DocumentResponse]` |
| 47 | POST | `/master-data` | — | Add a master-data value (`FOUNDATION_MANAGE`, 201) | `MasterDataResponse` |
| 48 | PATCH | `/master-data/{pk}` | — | Edit a master-data value (`FOUNDATION_MANAGE`) | `MasterDataResponse` |
| 49 | POST | `/settings` | — | Add a system setting (`FOUNDATION_MANAGE`, 201) | `SettingResponse` |
| 50 | PATCH | `/settings/{key}` | — | Edit a system setting (`FOUNDATION_MANAGE`) | `SettingResponse` |
| 51 | POST | `/sequences` | — | Add an ID sequence (`FOUNDATION_MANAGE`, 201) | `SequenceResponse` |
| 52 | PATCH | `/sequences/{sequence_code}` | — | Edit an ID sequence (`FOUNDATION_MANAGE`) | `SequenceResponse` |
| 109 | GET | `/sakha-postal-codes` | `state_pk`, `district_pk`, `postal_code_pk` | Sakha-to-postal-code links (`FOUNDATION_VIEW`) | `list[SakhaPostalCodeResponse]` |
| 110 | GET | `/festivals` | — | Active festivals that can carry calendar dates (`FOUNDATION_VIEW`) | `list[FestivalMasterResponse]` |
| 111 | GET | `/festival-calendar-dates` | `festival_code`, `calendar_year` | Observed festival dates, newest year first (`FOUNDATION_VIEW`) | `list[FestivalCalendarDateResponse]` |
| 112 | POST | `/festival-calendar-dates` | — | Record a festival/year date (`FOUNDATION_CALENDAR_MANAGE`, NSS_ERP_ADMIN only, 201) | `FestivalCalendarDateResponse` |
| 113 | PATCH | `/festival-calendar-dates/{pk}` | — | Edit an observed date (`FOUNDATION_CALENDAR_MANAGE`) | `FestivalCalendarDateResponse` |
| 121 | GET | `/post-offices` | `postal_code_pk` (required) | Active APPROVED post offices under a PIN (`FOUNDATION_VIEW`) | `list[PostOfficeResponse]` |
| 122 | POST | `/districts/propose` | — | Member proposes an unseen district for a state; stored `entry_status='PENDING'` (`get_current_user`; caller must hold an active Sangha Sevi, else 403; 201) | `PendingDistrictResponse` |
| 123 | POST | `/postal-codes/propose` | — | Same, for a PIN (201) | pending-row response |
| 124 | POST | `/post-offices/propose` | — | Same, for a post office under a PIN (201) | pending-row response |
| 125 | POST | `/city-villages/propose` | — | Same, for a city/village (201) | pending-row response |

Endpoints 47-52, 109-113 and 121-125 are numbered out of sequence (after the Tier 4 numbering) for the same reason as
`/children-stats` below. See `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` §3.4.

---

# 5. Tier 2 — Organization

**Router prefix:** `/api/v1/organization` — all 8 endpoints gated by
`require_permission("ORGANIZATION_VIEW")`.

| # | Method | Path | Filters | Description | Response Model |
|---|---|---|---|---|---|
| 22 | GET | `/types` | — | List organization types | `list[OrganizationTypeResponse]` |
| 23 | GET | `/statuses` | — | List lifecycle statuses | `list[StatusResponse]` |
| 24 | GET | `/organizations` | `type_code`, `status_code`, `limit`, `offset` | List organizations | `list[OrganizationResponse]` |
| 25 | GET | `/organizations/{pk}` | — | Organization detail | `OrganizationResponse` |
| 26 | GET | `/organizations/{pk}/children` | — | Direct children of org | `list[OrganizationResponse]` |
| 27 | GET | `/hierarchy` | `limit`, `offset` | Recursive org tree | `list[OrganizationHierarchyNodeResponse]` |
| 43 | GET | `/organizations/{pk}/children-stats` | — | Per-direct-child family/member/person counts (dynamic Sakha majority rule, FAM-036) | `list[OrgChildStatsResponse]` |
| 114 | GET | `/organizations/selectable` | `type_code` (repeatable), `country_pk`, `state_pk`, `district_pk`, `postal_code_pk`, `limit`, `offset` | Member-facing active-org lookup for dropdowns; auth only, not `ORGANIZATION_VIEW` | `list[OrganizationResponse]` |
| 115 | GET | `/organizations/{pk}/wings` | — | Wing-body summary (member count per wing; only MAHILA_SANGHA reports a count) (`ORGANIZATION_VIEW`) | `OrgWingSummaryResponse` |
| 116 | GET | `/organizations/{pk}/wings/{wing_type_code}/members` | `limit`, `offset` | Wing roster across the subtree; 422 for KUMARI_SANGHA/SEVAK_SANGHA (`ORGANIZATION_VIEW`) | `WingMemberListResponse` |
| 53 | GET | `/organizations/{pk}/stats` | — | Whole-subtree totals for the org itself (`member_count`, `family_count`, `sakha_sanghas`, `mahila_sanghas`, `renewals_due`; member/family counts use the same FAM-036 majority rule as `/children-stats`); 403 if the org is outside the caller's admin scope (ADMIN-BR-076); backs the Org Dashboard | `OrgStatsResponse` |

**Note:** `/children-stats` (Tier 4, added on top of Family + Membership) is numbered out of
the original 22–27 sequence to avoid renumbering every endpoint added after Tier 2 in this
table; see `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` §3.2.4 for the full contract.

---

# 6. Tier 3 — Person

**Router prefix:** `/api/v1/person`

| # | Method | Path | Filters | Description | Response Model |
|---|---|---|---|---|---|
| 28 | GET | `/persons` | `gender_code`, `marital_status_code`, `blood_group_code`, `limit`, `offset` | List persons (summary) | `PersonListResponse` (`{persons, total}`, see §2.1) |
| 29 | GET | `/persons/{pk}` | — | Person detail (with aadhaar_last4) | `PersonDetailResponse` |
| 30 | GET | `/persons/{pk}/addresses` | — | Person addresses | `list[PersonAddressResponse]` |
| 120 | GET | `/search-selectable?q=` | `q` (min 2 chars, required), `limit` (default 50), `offset` | Same search as #31 but gated on authentication only, for the family-head add-member picker | `PersonListResponse` |
| 31 | GET | `/search?q=` | `q` (min 2 chars, required), `limit` (default 50), `offset` | Trigram + prefix search across name + ID + contact | `PersonListResponse` (`{persons, total}`, see §2.1) |

**Auth:** list (#28) and search (#31) require `require_permission("PERSON_VIEW")`; detail (#29)
and addresses (#30) use `get_current_user` plus an ownership check — the person themself or a
holder of `PERSON_VIEW`. A separate `PERSON_VIEW_SENSITIVE` permission is seeded but not wired to
any endpoint (Aadhaar masking is unconditional).

**Security notes:**

- Summary endpoints exclude `aadhaar_last4`, `aadhaar_encrypted`, `aadhaar_hash`
- Detail includes `aadhaar_last4` (masked in UI as `XXXX XXXX <last4>`)
- `aadhaar_encrypted` and `aadhaar_hash` are never exposed via API

---

# 7. Tier 4 — Family

**Router prefix:** `/api/v1/family` — 16 endpoints (7 original reads, 1 new read, 8 Tier 5
writes). **All use `get_current_user` plus an ownership model**, not a blanket permission: a
person reaches their own family through their `family_relationship`/`family_admin` row
(`_require_family_view`/`_require_family_manage`/`_require_family_head`), with
`FAMILY_VIEW`/`FAMILY_MANAGE` as the admin override for families the caller doesn't belong to;
`GET /families` (browse-all) requires `FAMILY_VIEW` outright. Writes use `get_write_connection`.

| # | Method | Path | Filters | Description | Response Model |
|---|---|---|---|---|---|
| 32 | GET | `/families` | `sakha_code`, `status_code`, `limit`, `offset` | List families | `list[FamilyGroupResponse]` |
| 33 | GET | `/families/{pk}` | — | Family detail | `FamilyGroupResponse` |
| 34 | GET | `/families/{pk}/members` | — | Current family members | `list[FamilyMemberResponse]` |
| 35 | GET | `/families/{pk}/head-history` | — | Family head history | `list[FamilyHeadHistoryResponse]` |
| 44 | GET | `/families/{pk}/graph` | `viewer_person_pk` (required) | Dynamic per-viewer relationship labels via BFS graph traversal over `family_link` (PARENT_OF/SPOUSE_OF edges) | `list[FamilyGraphMemberResponse]` |
| 45 | GET | `/families/{pk}/sakha-alignment` | — | FAM-036 majority-rule "effective Sakha" for the family, per-Sakha member counts, per-member mismatch flags | `FamilySakhaAlignmentResponse` |
| 46 | GET | `/person/{person_pk}/membership-summary` | — | Lightweight membership snapshot for a person (sangha_sevi_id, type/status, current Sakha, latest Parichaya/Anumati Patra); bridges family context to membership context; access: the person, a current relative, or `FAMILY_VIEW` | `PersonMembershipSummaryResponse` |

Tier 5 additions (numbered 55-63, see the continuation table at the end of this section):

| # | Method | Path | Rule | Description |
|---|---|---|---|---|
| 55 | GET | `/person/{person_pk}/families` | the person, a current relative, or `FAMILY_VIEW` | Families a person belongs to |
| 56 | POST | `/families` | any authenticated user | Create a family; caller becomes founding member + head (`SELF` relationship), `family_id` auto-generated |
| 57 | POST | `/families/{pk}/members` | head / family admin / `FAMILY_MANAGE` | Add a member |
| 58 | DELETE | `/families/{pk}/members` | head / family admin / `FAMILY_MANAGE` | Remove a member (FAM-048) |
| 59 | POST | `/families/{pk}/links` | head / family admin / `FAMILY_MANAGE` | Create `family_link` graph edges |
| 60 | GET | `/families/{pk}/admins` | family view rule | List `family_admin` rows |
| 61 | POST | `/families/{pk}/admins` | current head / `FAMILY_MANAGE` | Assign a Family Admin (FAM-046) |
| 62 | DELETE | `/families/{pk}/admins` | current head / `FAMILY_MANAGE` | Revoke a Family Admin (FAM-050) |
| 63 | POST | `/families/{pk}/transfer-head` | current head only | Transfer the head role |

**Note:** `/graph`, `/sakha-alignment`, and `/person/{pk}/membership-summary` are numbered
out of the original 32–35 sequence, following the same out-of-sequence numbering convention
used for Organization's `/children-stats` (§5) — added after Tier 4 Membership without
renumbering earlier endpoints.

**Notes:**

- Members endpoint returns only `is_current=TRUE` relationships
- Head history ordered by `effective_from DESC` (most recent first)
- Sub-resource endpoints return `404` if the parent family does not exist
- `/graph` returns `404` if the family does not exist; returns `[]` if the family has no
  `family_link` rows (no graph data) even though it has members
- `/graph`'s BFS traversal caps at `max_depth=6` (see `api/services/family_graph.py`); path
  patterns not in the `PATH_LABELS` lookup table degrade to a generic `"Relative"` label
  rather than erroring
- `/sakha-alignment`'s `is_aligned` is always `true` by construction — the family's
  "effective" Sakha is *defined* as the majority, so it cannot disagree with itself; per-member
  `is_home_sakha` is the field that actually flags a mismatch
- `/person/{pk}/membership-summary` returns an all-empty-fields `200` (not `404`) when the
  person has no `sangha_sevi` record — the person PK itself is not validated against `person`
- Anumati Patra is omitted from the membership summary when `membership_type_code == "ASSOCIATE"`
  (MBR-019A/B)

---

# 8. Tier 4 — Membership

**Router prefix:** `/api/v1/membership` — 8 endpoints. List (#36), search (#38) and
`darshak-summary` (#54) require `require_permission("MEMBERSHIP_VIEW")`; member detail (#37) and
the four per-member sub-resources (#39-#42) use `get_current_user` with a "self or
`MEMBERSHIP_VIEW`" ownership check (`require_self_or_permission()`), so a member can read their
own Member Dashboard data.

| # | Method | Path | Filters | Description | Response Model |
|---|---|---|---|---|---|
| 36 | GET | `/members` | `type_code`, `status_code`, `org_code`, `org_type_code`, `limit`, `offset` | List members | `MemberListResponse` (`{members, total}`, see §2.1) |
| 37 | GET | `/members/{pk}` | — | Member detail | `MemberResponse` |
| 38 | GET | `/search?q=` | `q` (min 2 chars, required), `limit` (default 50), `offset` | Trigram + prefix search across all 3 identity tiers + name + contact | `MemberListResponse` (`{members, total}`, see §2.1) |
| 39 | GET | `/members/{pk}/affiliations` | — | Sakha affiliation history | `list[SakhaAffiliationResponse]` |
| 40 | GET | `/members/{pk}/parichaya-patra` | — | Parichaya Patra records | `list[ParichayaPatraResponse]` |
| 41 | GET | `/members/{pk}/anumati-patra` | — | Anumati Patra records | `list[AnumatiPatraResponse]` |
| 42 | GET | `/members/{pk}/journey` | — | Journey events (chronological) | `list[JourneyEventResponse]` |
| 54 | GET | `/organizations/{org_pk}/darshak-summary` | — | Two counts for an org's Darshak card: `home_probationary_count` (active Probationary members whose home Sakha is the org) and `attending_from_other_sakha_count` (cross-Sakha Darshak attendance affiliations, SOL-MEM-006) | `OrgDarshakSummaryResponse` |

**Search fields (endpoint #31 — Person):**

| Field | Match Type | Source Table |
|---|---|---|
| `person_id` (P1) | Prefix (ILIKE) | `person` |
| `first_name`, `last_name` | Trigram (`pg_trgm`, threshold 0.45) | `person` |
| `mobile_number` | Prefix (ILIKE) | `person` |
| `email` | Prefix (ILIKE) | `person` |

**Search fields (endpoint #38 — Membership):**

| Field | Match Type | Source Table |
|---|---|---|
| `sangha_sevi_id` (SS1) | Prefix (ILIKE) | `sangha_sevi` |
| `person_id` (P1) | Prefix (ILIKE) | `person` |
| `local_sakha_erp_id` (ESS1192) | Prefix (ILIKE) | `membership_sakha_affiliation` (active) |
| `first_name`, `last_name` | Trigram (`pg_trgm`) | `person` |
| `mobile_number` | Prefix (ILIKE) | `person` |
| `email` | Prefix (ILIKE) | `person` |
| `document_number` (345/2026/2027) | Prefix (ILIKE) | `parichaya_patra` (any status) |

**Three-tier identity in responses:**

```text
Tier 1: sangha_sevi_id        — on MemberResponse (permanent)
Tier 2: local_sakha_erp_id    — on MemberResponse (current, from active affiliation)
                                 on SakhaAffiliationResponse (per-period)
                                 on ParichayaPatraResponse (snapshot at issuance)
Tier 3: document_number       — on ParichayaPatraResponse (Kendra Number)
```

**Notes:**

- Email-like queries (containing `.` or `@`) use `re.split(r'[.@]', q)[0]` for
  trigram comparison parameters, preventing false positives (e.g. "aniket.mishra"
  would otherwise trigram-match "Ramesh Mishra" via the surname component)
- Affiliations ordered by `effective_from DESC`
- Parichaya Patra ordered by `valid_from DESC`
- Anumati Patra ordered by `valid_from DESC` — includes EXPIRED records for members
  who progressed from Probationary to Regular
- Journey events ordered by `event_date ASC` (chronological)
- Sub-resource endpoints return `404` if the parent member does not exist
- `membership_type_code` is returned as `PROBATIONARY` (UI displays as "Darshaka")

---

# 8b. Tier 6 — Membership Change Requests

**Router prefix:** `/api/v1/membership/change-requests` (`api/routers/membership_change_request.py`,
MBR-048 Sakha Transfer / MBR-049 Apply for Darshak) — 5 endpoints. A separate router from
`membership.py` because these are writes (auditing `get_write_connection`); `membership.py` stays
read-only. Workflow: `PENDING_SOURCE_RELEASE` -> source Sakha releases -> `PENDING_DESTINATION_ACCEPT`
-> destination accepts -> `COMPLETED`; either Sakha rejecting ends it (`REJECTED_BY_SOURCE` /
`REJECTED_BY_DESTINATION`). `request_type` is `TRANSFER` or `DARSHAK` (a Darshak request never
closes the home affiliation).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `` (base path) | `get_current_user`; self, or `MEMBERSHIP_MANAGE` for another member | File a request (`sangha_sevi_pk`, `request_type`, `new_organization_pk`, `transfer_reason`); 201 |
| GET | `` (base path) | `get_current_user`; `MEMBERSHIP_VIEW`/`MEMBERSHIP_APPROVE` = admin view (scoped), otherwise forced to own rows, 403 with no `sangha_sevi_pk` | List (`status`, `organization_pk`, `page`, `page_size` ≤ 100) |
| GET | `/{change_request_pk}` | `get_current_user` | Detail |
| POST | `/{change_request_pk}/source-decision` | `MEMBERSHIP_APPROVE` + old Sakha in scope | `decision` = `RELEASE`/`REJECT`, `remarks` |
| POST | `/{change_request_pk}/destination-decision` | `MEMBERSHIP_APPROVE` + new Sakha in scope | `decision` = `ACCEPT`/`REJECT`, `remarks`; auto-numbers via `next_sakha_local_number()`, or `is_legacy_import` + `new_local_number` for a paper-register number |

Also in Tier 6: `GET /api/v1/membership/search` gained an optional `organization_pk` filter
(subtree-aware on `sangha_sevi.organization_pk`) used by governance nominee/voter pickers.

---

# 9. Tier 5 — Authentication

**Router prefix:** `/api/v1/auth` — 10 endpoints. JWT with a stateful `nss.user_session` row per login (Tier 5
A4; `logout` and `DELETE /sessions/{session_pk}` revoke it); Argon2 password hashing; 5-attempt/30-second login lockout.

| # | Method | Path | Auth | Description |
|---|---|---|---|---|
| 64 | POST | `/login` | none | Login with Sangha Sevi ID or Person ID (case-insensitive) → access + refresh JWT |
| 65 | POST | `/refresh` | refresh token | Issue a new access token |
| 66 | POST | `/logout` | JWT | Revokes the caller's `user_session` (no-op for pre-A4 tokens without `session_pk`) |
| 67 | POST | `/change-password` | JWT | Change own password (history-checked) |
| 68 | POST | `/forgot-password` | none | Issue a 6-digit OTP; rate-limited 3/hour, anti-enumeration generic response; `otp_debug` echoed only if `DEBUG_MODE=true` |
| 69 | POST | `/reset-password` | OTP | Reset password with the OTP |
| 70 | GET | `/me` | JWT | Current user, roles, permissions, admin scope |
| 71 | PATCH | `/profile` | JWT | Update own profile fields |
| 134 | GET | `/sessions` | JWT | List own active (non-revoked, unexpired) sessions; `is_current` marks the caller's own |
| 135 | DELETE | `/sessions/{session_pk}` | JWT | Revoke one of own sessions (generic 404 if absent or not owned) |

---

# 10. Tier 5 — Registration (public)

**Router prefix:** `/api/v1/register` — 12 endpoints, all deliberately unauthenticated (the
registration page has no JWT yet). `POST ""` always creates a `person`; it creates
`user_account(PENDING_APPROVAL)` + `registration_claim` **only when `has_membership` is true**
(a membership-less registrant gets no account — it could never log in — and the typed password is
discarded). Such a person can later submit a claim through `/lookup-existing` + `/claim`, verified
by `person_id` + date of birth. **No `sangha_sevi` is created until an admin approves the claim.**

| # | Method | Path | Description |
|---|---|---|---|
| 72 | POST | `` | Self-register |
| 73 | POST | `/check-duplicate` | Pre-submit contact-uniqueness check |
| 136 | POST | `/lookup-existing` | Verify a previously-registered, Sangha-Sevi-less person by `person_id` + `date_of_birth` (404 on mismatch; 409 if an account, pending claim or active Sangha Sevi already exists) |
| 137 | POST | `/claim` | Create `user_account(PENDING_APPROVAL)` + `registration_claim` for that person (re-verifies `person_id` + DOB; 201, same `RegisterResponse` as register) |
| 74 | GET | `/reference-data` | Countries, gender/marital-status/blood-group/membership-type master data and the Sakha list in one call |
| 75 | GET | `/states` | States for a country |
| 76 | GET | `/districts` | Districts for a state |
| 77 | GET | `/postal-codes` | Postal codes (`state_pk`, `country_pk` filters) |
| 117 | GET | `/countries` | Countries, so authenticated member screens can avoid the admin-only `FOUNDATION_VIEW` |
| 118 | GET | `/cities` | Cities/villages for a district (suggestions, not a hard-restricted list) |
| 119 | GET | `/sakhas` | "Find my Sakha": active Sakha Sangha list filtered by `country_pk`/`state_pk`/`district_pk`/`postal_code_pk` (max 500) |
| 126 | GET | `/post-offices` | Post offices under a PIN (`postal_code_pk`, required) — suggestions for the registration location cascade; a typed name not on file is created on submit via `resolve_or_create_post_office()` |

---

# 11. Tier 5 — Claim Approval

**Router prefix:** `/api/v1/admin/claims` — 5 endpoints, all
`require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")`; list/detail are scoped to the
admin's `admin_scope` organizations unless NSS-WIDE.

| # | Method | Path | Description |
|---|---|---|---|
| 78 | GET | `` | List claims (status filter, pagination, sorting) |
| 79 | GET | `/{pk}` | Claim detail |
| 80 | PATCH | `/{pk}` | Edit claim fields before decision |
| 81 | POST | `/{pk}/approve` | Approve — creates `sangha_sevi` + `membership_sakha_affiliation`, activates the account |
| 82 | POST | `/{pk}/reject` | Reject the claim |

---

# 12. Tier 5 — Administration

**Router prefix:** `/api/v1/admin` — 32 endpoints (28 Tier 5 + 4 Tier 6 credential endpoints). Permission sets per endpoint are listed in
the last column (`any of`).

| # | Method | Path | Description | Permission (any of) |
|---|---|---|---|---|
| 83 | GET | `/users` | List users (search, sort, pagination); only accounts tied to an active `sangha_sevi` | `ADMIN_USER_VIEW`, `ADMIN_USER_MANAGE`, `MEMBERSHIP_APPROVE` |
| 84 | POST | `/users` | Create a user account | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 85 | GET | `/users/{pk}` | User detail | view set above |
| 86 | GET | `/users/check-account/{person_pk}` | Does a person already have a usable/soft-deleted login | `ADMIN_USER_VIEW`, `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 87 | POST | `/users/{pk}/reset-password` | Admin password reset | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 88 | PATCH | `/users/{pk}/status` | Activate / suspend / etc. — only sets `account_status`; ACTIVE from `PENDING_APPROVAL` is 422 if a PENDING claim exists or the person has no active `sangha_sevi` | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 89 | DELETE | `/users/{pk}` | Soft-delete a user | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 90 | GET | `/users/{pk}/roles` | List role assignments | view set above |
| 91 | POST | `/users/{pk}/roles` | Assign a role (with scope) | `ADMIN_ROLE_MANAGE` |
| 92 | DELETE | `/users/{pk}/roles/{user_role_pk}` | Revoke a role assignment | `ADMIN_ROLE_MANAGE` |
| 93 | POST | `/persons` | Create a person (no account) | `PERSON_MANAGE` |
| 94 | GET | `/persons/check-contact` | Advisory duplicate-contact lookup | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 95 | POST | `/sangha-sevi` | Provision a Sangha Sevi ID for a person | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 96 | GET | `/sangha-sevi/check/{person_pk}` | Does the person already hold an SS ID | view set above |
| 97 | POST | `/sangha-sevi/check-batch` | Batch form of the above | view set above |
| 98 | GET | `/sangha-sevi/without-account` | Paginated list of Sangha Sevis who can't log in yet | view set above |
| 99 | GET | `/organizations` | Org list for admin screens | view set above |
| 100 | POST | `/organizations` | Create an organization (ORG-BR-099/101-103 rules) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 101 | PATCH | `/organizations/{pk}` | Edit an org incl. `parent_organization_pk` re-parenting; subtree-scoped (ADMIN-BR-076/077) | `ORGANIZATION_MANAGE`, `ORGANIZATION_VIEW` |
| 102 | PATCH | `/organizations/{pk}/short-code` | Edit the org short code; same subtree scoping | `ORGANIZATION_MANAGE`, `ORGANIZATION_VIEW` |
| 103 | GET | `/organizations/kumari-sevak-sakha-options` | Sakha choices for Kumari/Sevak orgs (ORG-BR-101/102) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 104 | GET | `/sakha-scope-options` | Sakha scope choices (ORG-BR-103) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 105 | GET | `/organizations/code-availability` | Is an org code free | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 106 | GET | `/organizations/next-code` | Sequence-driven code preview | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 107 | GET | `/dashboard-stats` | Counts scoped to the viewer's own admin scope | view set above |
| 127 | GET | `/persons/{pk}` | Raw editable field values for the Profile Details edit card (person must be inside the actor's scope) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 128 | PATCH | `/persons/{pk}` | Admin correction of a member's personal-info fields (same validation as registration; only non-null fields applied) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
| 129 | PATCH | `/patra/{patra_type}/{patra_pk}/document-number` | Correct the number on an issued Patra (`patra_type` = `parichaya` or `anumati`; MBR-030H; audit-logged old/new; Patra's Sakha must be in scope) | `MEMBERSHIP_MANAGE`, `ADMIN_USER_MANAGE` |
| T6 | GET | `/credentials/members` | Per-member credential health, one row per active Sangha Sevi (`state` = OK/EXPIRING/LAPSED/MISSING, `membership_type`, `search`, `page`, `page_size` ≤ 200; EXPIRING = `valid_to` within 60 days; MBR-019B; scoped, ADMIN-BR-076) | `MEMBERSHIP_VIEW`, `MEMBERSHIP_MANAGE`, `ADMIN_USER_MANAGE` |
| T6 | GET | `/credentials/members/{sangha_sevi_pk}/timeline` | Full Anumati + Parichaya credential history for one member, oldest first (`CredentialTimelineResponse`) | `MEMBERSHIP_VIEW`, `MEMBERSHIP_MANAGE`, `ADMIN_USER_MANAGE` |
| T6 | POST | `/credentials/members/{sangha_sevi_pk}/issue` | Issue/renew the one credential the member should hold, optional manual number (MBR-030H); 201 | `MEMBERSHIP_MANAGE`, `ADMIN_USER_MANAGE` |
| T6 | POST | `/credentials/members/{sangha_sevi_pk}/promote` | Promote Darshaka to Regular: expire the Anumati Patra, issue the Parichaya Patra (MBR-010) | `MEMBERSHIP_MANAGE`, `ADMIN_USER_MANAGE` |

`GET /users/{pk}` additionally returns read-only `auto_granted_scopes` (§63 composite auto-grants,
derived live by `rbac_service.load_composite_grants()`; no `user_role_pk`, nothing revocable).

Scope rule for both org `PATCH` endpoints: `NSS_ERP_ADMIN`/NSS-WIDE edits any org; any other
scoped admin edits only organizations inside their own scope subtree, regardless of which
permission they hold.

---

# 12b. Tier 5 — Geo-Entry Approval

**Router prefix:** `/api/v1/admin/geo-entries` (`api/routers/geo_approval.py`, Member-Assisted Geographic
Entry, SOL-ARCH-010 Amendment 2026-10-03) — 4 endpoints, all `FOUNDATION_MANAGE`, scope-filtered
(ADMIN-BR-076, anchored on the submitter's `sangha_sevi.organization_pk`). `{entity}` is one of
`district`, `postal-code`, `post-office`, `city-village`.

| # | Method | Path | Description |
|---|---|---|---|
| 130 | GET | `/{entity}` | List member-submitted entries (`status` = `PENDING` default / `APPROVED` / `CORRECTED`, `page`, `page_size` ≤ 100) |
| 131 | GET | `/{entity}/{entry_pk}` | Entry detail (404 / 403 outside scope) |
| 132 | POST | `/{entity}/{entry_pk}/approve` | PENDING → APPROVED (422 if not pending, 409 on duplicate of an approved row) |
| 133 | POST | `/{entity}/{entry_pk}/correct` | Find-or-create the canonical row, mark the entry CORRECTED and re-point dependent `person_address` FKs |

---

# 12c. Tier 6 — Governance

**Router prefix:** `/api/v1/governance` (`api/routers/governance.py`, Unified Body Governance,
SOL-GOV-002/004) — 46 endpoints. Gates: `GOVERNANCE_VIEW` + `GOVERNANCE_MANAGE` are the two new
permissions. "View" below means `require_any_permission("GOVERNANCE_VIEW","GOVERNANCE_MANAGE")`;
"Manage" means `require_permission("GOVERNANCE_MANAGE")`; "Login" is plain `get_current_user`.
A body/election with `organization_pk IS NULL` is NSS-wide and manageable only by `NSS_ERP_ADMIN`/NSS-WIDE;
org-scoped ones go through the subtree scope check (ADMIN-BR-076/077).

| Method | Path | Gate | Description |
|---|---|---|---|
| GET | `/bodies/sakha-scope-options` | Manage | Parent-Sakha picker data for Sakha-anchored bodies, scoped by the actor's admin scope (query `body_type_master_pk`) |
| GET | `/me/parichalak-status` | Login | Whether the caller currently holds the NSS-wide Parichalak seat (GOV-BR-043-A) |
| GET | `/body-types` | View | Body-type catalogue |
| POST | `/body-types` | Manage | Create (201) |
| PATCH | `/body-types/{body_type_master_pk}` | Manage | Update |
| DELETE | `/body-types/{body_type_master_pk}` | Manage | Deactivate (soft) |
| GET | `/positions` | View | Position catalogue |
| POST | `/positions` | Manage | Create (201) |
| PATCH | `/positions/{position_master_pk}` | Manage | Update |
| DELETE | `/positions/{position_master_pk}` | Manage | Deactivate (soft) |
| GET | `/bodies` | View | List bodies (`BodyListResponse`) |
| GET | `/bodies/{body_master_pk}` | View | Body detail |
| POST | `/bodies` | Manage | Create (201) |
| PATCH | `/bodies/{body_master_pk}` | Manage | Update |
| DELETE | `/bodies/{body_master_pk}` | Manage | Deactivate (soft) |
| GET | `/public/national-bodies` | Login | Up to 4 bodies with current composition: the NSS-wide Kendra GB, Advisory Board, central Mahila Parichalana Mandali, plus the viewer's own Sakha GB (dashboard Governance tab) |
| GET | `/public/sakha-office-bearers` | Login | Per-Sakha President and Secretary (with mobile) for the Find-a-Sakha directory |
| GET | `/bodies/{body_master_pk}/assignments` | View | Member assignments of a body |
| GET | `/bodies/{body_master_pk}/allowed-positions` | View | Positions the body may hold, seat limit and seats filled |
| GET | `/bodies/{body_master_pk}/inherited-positions` | View | Read-only office-holders inherited from another body (empty for most types) |
| GET | `/advisory-board/missing-nominations` | View | Active Sakha Sanghas with no current Advisory Board MEMBER nomination (NSS-wide admins only) |
| GET | `/mukhya-pujaka` | View | The single NSS-wide Mukhya Pujaka post, hosting body, current holder |
| POST | `/bodies/{body_master_pk}/assignments` | Manage | Assign a member to a position (201; composition, singleton, membership, seat-limit checks) |
| POST | `/assignments/{body_member_assignment_pk}/end` | Manage | End an assignment |
| POST | `/assignments/{body_member_assignment_pk}/resign` | Login | Voluntary self-withdrawal; only the person named on the assignment may call it (no permission/scope override); sets `RESIGNED` |
| POST | `/assignments/{body_member_assignment_pk}/request-removal` | Manage | Forced-removal request for a Sakha-nominated representative (super-admin break-glass; sets `PENDING_REMOVAL`) |
| POST | `/assignments/{body_member_assignment_pk}/approve-removal` | Manage | Approve a pending removal (body's own sitting President only) |
| POST | `/assignments/{body_member_assignment_pk}/reject-removal` | Manage | Reject a pending removal (body's own sitting President only) |
| GET | `/bodies/{body_master_pk}/acting-assignments` | View | Acting assignments |
| POST | `/bodies/{body_master_pk}/acting-assignments` | Manage | Create an acting assignment (201) |
| POST | `/acting-assignments/{acting_position_assignment_pk}/end` | Manage | End an acting assignment |
| GET | `/elections` | View | List elections |
| GET | `/elections/open-for-voting` | Login | Elections in VOTING this member may vote in (registered before `/elections/{election_pk}`) |
| GET | `/elections/{election_pk}` | View | Election detail |
| POST | `/elections` | Manage | Create (201) |
| PATCH | `/elections/{election_pk}/status` | Manage | Advance election status |
| GET | `/elections/{election_pk}/nominations` | View | List nominations |
| POST | `/elections/{election_pk}/nominations` | Manage | File a nomination (201) |
| PATCH | `/nominations/{election_nomination_pk}/status` | Manage | Accept/reject a nomination |
| POST | `/elections/{election_pk}/votes` | Manage | Officer-recorded vote (201) |
| POST | `/elections/{election_pk}/votes/self` | Login | Member casts their own ballot (201; voter taken from session, GOV-BR-043/045) |
| POST | `/elections/{election_pk}/votes/reset` | Manage | Hard-delete cast ballots (President unilateral, or admin with President approval); whole election or one position |
| GET | `/elections/{election_pk}/tally` | View | Live tally |
| GET | `/elections/{election_pk}/results` | View | Declared results |
| POST | `/elections/{election_pk}/results` | Manage | Declare a result (201) |
| POST | `/results/{election_result_pk}/apply` | Manage | Hand a declared winner off into a live `body_member_assignment` |

**§63 composite auto-grant.** Certain governance positions grant admin RBAC automatically,
computed live (nothing stored) by `rbac_service.load_composite_grants()` and merged into the
caller's scopes/permissions: Kendra GB members (all) -> `NSS_ERP_KENDRA_ADMIN`; Advisory Board
President/Secretary -> `NSS_ERP_ADVISORY_BOARD_ADMIN`; Sakha GB / Sevak Sangha Executive /
Anchalika / Zilla / Patha Chakra GB President and Secretary -> the matching org-scoped admin
role; Mahila Parichalana Mandali President/Joint Secretary -> `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`
(central) or `NSS_ERP_SAKHA_ADMIN` (per Sakha). Acting holders are added when not already covered.

---

# 12d. Tier 6 — Correspondence Register

**Router prefix:** `/api/v1/correspondence` (`api/routers/correspondence.py`, SOL-ADMIN-009) — 9
endpoints. Gates: `CORRESPONDENCE_VIEW` + `CORRESPONDENCE_MANAGE` are the two new permissions,
scoped to the record's `register_organization_pk` via `require_org_in_scope()`/
`actor_scope_org_pks()` — the same admin-scope model as Foundation/Person/Membership, not the
NSS-wide-only Governance footprint. "View" below means
`require_any_permission("CORRESPONDENCE_VIEW","CORRESPONDENCE_MANAGE")`; "Manage" means
`require_permission("CORRESPONDENCE_MANAGE")`.

| Method | Path | Gate | Description |
|---|---|---|---|
| POST | `/` | Manage | Register a new inward/outward entry (201); `reference_number` is minted server-side (CORR-EXT-001), initial status always `REGISTERED` |
| GET | `/` | View | List, scoped to the caller's admin-scope register(s); filters `register_organization_pk`, `direction`, `status` |
| GET | `/{correspondence_pk}` | View | Detail |
| POST | `/{correspondence_pk}/transition` | Manage | Move to a new status per the §6.2 seven-row precondition table; reopening (ACTIONED/CLOSED → PENDING_ACTION) requires non-empty `remarks` (§6.3); always timestamped `NOW()` (§6.4) |
| POST | `/{correspondence_pk}/responsible-party` | Manage | Assign/clear the responsible person or organization (§5.4); permitted at any status, never itself a transition |
| POST | `/{correspondence_pk}/documents` | Manage | Associate a `document_master` row under a purpose (ORIGINAL/RESPONSE/ATTACHMENT/SUPPORTING); 201 |
| GET | `/{correspondence_pk}/documents` | View | List associated documents |
| POST | `/{correspondence_pk}/finance-references` | Manage | Reference a Finance transaction (201); `financial_transaction_pk` existence is not yet enforced — Finance (Tier 12) does not exist yet, documented gap |
| GET | `/{correspondence_pk}/finance-references` | View | List finance references |

**Status lifecycle (§6.1):** `REGISTERED → PENDING_ACTION → ACTIONED → CLOSED`, with
`ACTIONED`/`CLOSED → PENDING_ACTION` reopen paths and `REGISTERED → ACTIONED`/`CLOSED` direct
paths; no other transition pair is valid. `REGISTERED → PENDING_ACTION` additionally requires a
responsible person/organization already set on the row.

---

# 13. Tier 5 — Audit

**Router prefix:** `/api/v1/audit` — 1 endpoint, `require_permission("AUDIT_VIEW")` (seeded to
`NSS_ERP_ADMIN`, `NSS_ERP_KENDRA_ADMIN`, `NSS_ERP_AUDITOR`), read-only pool.

| # | Method | Path | Filters | Description |
|---|---|---|---|---|
| 108 | GET | `/change-log` | `table_name`, `record_pk`, `field_name`, `changed_by_sangha_sevi_pk`, `changed_from`, `changed_to`, `limit`, `offset` | Paginated read of `nss.field_change_log` |

---

# 14. Frontend Routes

| Path | Description | HTML File |
|---|---|---|
| `/` | 302 redirect to `/login` | -- |
| `/login` | Login page | `login.html` |
| `/register` | Self-registration page | `register.html` |
| `/dashboard` | Member Dashboard (Personal, Membership, Family, Attendance, Governance, Documents tabs + an Org Dashboard for holders of an admin scope — tabs are built from the caller's role scopes) | `dashboard.html` |
| `/admin` | Administration console (Users, User Detail, Create User, Create Sangha-Sevi, Password, Create Organization, Organizations, Assign Sakhas, Registration Approvals, Geo Approvals, Person Directory, Member Directory, Organization Hierarchy, Org Dashboard, Reference Data, Geography, System Settings tabs) | `admin.html` |
| `/forgot-password` | **No standalone page by design** — the forgot/reset flow is inline on `/login` (`login.html`) | -- |
| `/docs` | Swagger UI (OpenAPI) | auto-generated |
| `/redoc` | ReDoc | auto-generated |

The six original Tier 0-4 verification-page routes (`/` → `index.html`, `/foundation`,
`/organization`, `/person`, `/family`, `/membership`) were retired along with their HTML/JS
files; each tier's UI now lives in a tab of `admin.html` or `dashboard.html` — Bootstrap RBAC →
System Settings, Foundation → Reference Data + Geography, Organization → Organizations +
Organization Hierarchy, Person → Person Directory, Family → `dashboard.html`'s Family tab,
Membership → `dashboard.html`'s Membership tab plus `admin.html`'s Member Directory tab.

Every served page has its `/assets/js/*.js` and `/assets/css/*.css` references rewritten to
`?v=<content hash>` per request (`api/main.py::_serve_page()`), so the long-cached assets never go
stale; the HTML itself is `Cache-Control: no-store`.

Frontend routes are excluded from OpenAPI schema (`include_in_schema=False`).

`/docs` and `/redoc` can be disabled via `DISABLE_DOCS=true` environment variable.

---

# 15. Endpoint Count Summary

| Tier | Module | Endpoints |
|---|---|---|
| 0 | Bootstrap | 4 |
| 1 | Foundation | 33 (21 read + 8 admin write + 4 member propose) |
| 2 | Organization | 11 |
| 3 | Person | 5 |
| 4 | Family | 16 (7 original read + 9 Tier 5) |
| 4 | Membership | 8 |
| 5 | Authentication | 10 |
| 5 | Registration | 12 |
| 5 | Claim Approval | 5 |
| 5 | Administration | 28 (+4 Tier 6 credential endpoints = 32) |
| 5 | Geo-Entry Approval | 4 |
| 5 | Audit | 1 |
| 6 | Governance | 46 |
| 6 | Membership Change Requests | 5 |
| 6 | Correspondence Register | 9 |
| **Total** | | **201** |

(137 + 4 admin credential + 46 + 5 + 9 = 201; per-router: admin 32, audit 1, auth 10, bootstrap 4, claim_approval 5, correspondence 9, family 16, foundation 33, geo_approval 4, governance 46, membership 8, membership_change_request 5, organization 11, person 5, registration 12.)

The endpoint numbers in the tables above are stable identifiers, not path order: #1-#46 are the
original Tier 0-4 set; #47-#137 were appended as Tier 5 endpoints landed. Tier 6 endpoints (sections 8b, 12c and the `T6` admin rows) are not numbered.

---

# End of Document
