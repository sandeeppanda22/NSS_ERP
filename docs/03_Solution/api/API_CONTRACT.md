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

The NSS ERP exposes a REST API (FastAPI, raw `psycopg2`, no ORM) of **284 endpoints** across 19
routers (252 / 17 on `develop`; the 26-endpoint Assets & Property router is committed on `feature/tier6-governance`, not yet merged; counts re-verified 2026-11-05 from the registered routes: 272 decorators + 12 `add_api_route`). Tiers 0-4 were originally read-only and unauthenticated; **Tier 5
(released as v0.11.0)** added JWT authentication, RBAC, write endpoints, and gated almost everything:

- **Only the 4 Tier 0 `bootstrap.py` endpoints and the 13 `/api/v1/register` endpoints (public
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

**Tier 6 (on `feature/tier6-governance`, not yet merged or released)** adds `governance.py` (56
endpoints, section 12c), `membership_change_request.py` (5, section 8b), `correspondence.py`
(19, section 12d), four admin credential endpoints (the `T6` rows in section 12) and
`membership.py`'s `GET /directory`. It also adds `attendance.py` (21, section 12e) and `org_reparent.py` (4, section 12f; the latter and the 2026-10-30/31 person-address / `/register/address-types` additions are committed on `feature/tier6-governance`).

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
| — | GET | `/organizations/in-scope` | `search`, `type_code` (repeatable), `limit`, `offset` | Scope-filtered (`actor_scope_org_pks`) searchable org list for the admin Correspondence pickers (`ORGANIZATION_VIEW`) | `list[OrganizationResponse]` |
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
| 29 | GET | `/persons/{pk}` | — | Person detail; `aadhaar_last4`/`aadhaar_full_on_file` null unless self or `PERSON_VIEW_SENSITIVE` in admin scope (GDR-011) | `PersonDetailResponse` |
| 30 | GET | `/persons/{pk}/addresses` | — | Person addresses | `list[PersonAddressResponse]` |
| 30a | POST | `/persons/{pk}/addresses` | — | Add an address (201); body `PersonAddressCreateRequest` | `PersonAddressResponse` |
| 30b | PATCH | `/persons/{pk}/addresses/{person_address_pk}` | — | Partial address update; body `PersonAddressUpdateRequest` | `PersonAddressResponse` |
| 30c | DELETE | `/persons/{pk}/addresses/{person_address_pk}` | — | Soft-delete an address | `MessageResponse` |
| 30d | GET | `/persons/{pk}/aadhaar` | — | **Aadhaar reveal (GDR-011, Proposed):** `PERSON_VIEW_SENSITIVE` + admin scope; decrypted 12 digits; 403 for the person themself and for everyone else; 404 `Full Aadhaar not on record`; 429 per-user (`AADHAAR_REVEAL_RATE_LIMIT`, default 10/min); 500 (no value) if decryption fails; audited as `VIEW_SENSITIVE` without the value | `PersonAadhaarResponse` (`{person_pk, aadhaar_number}`) |
| 120 | GET | `/search-selectable?q=` | `q` (min 2 chars, required), `limit` (default 50), `offset` | Same search as #31 but gated on authentication only, for the family-head add-member picker | `PersonListResponse` |
| 31 | GET | `/search?q=` | `q` (min 2 chars, required), `limit` (default 50), `offset` | Trigram + prefix search across name + ID + contact | `PersonListResponse` (`{persons, total}`, see §2.1) |

**Auth:** list (#28) and search (#31) require `require_permission("PERSON_VIEW")`; detail (#29)
and addresses (#30) use `get_current_user` plus an ownership check — the person themself or a
holder of `PERSON_VIEW`. A separate `PERSON_VIEW_SENSITIVE` permission is seeded but not wired to
any endpoint (Aadhaar masking is unconditional).

**Address writes (#30a-#30c):** `get_current_user` plus the person themself, or `PERSON_MANAGE`
within admin scope (ADMIN-BR-076). Geography FKs (`city_village_pk`, `postal_code_pk`,
`post_office_pk`) must be APPROVED, or PENDING and proposed by the address owner (registration
`submitted_by_person_pk`, or `submitted_by_sangha_sevi_pk` of one of their Sangha Sevi rows).
At most one active primary (`uq_person_primary_address`): the first address is auto-primary,
`is_primary=true` demotes the old primary, and the primary cannot be un-primaried or removed
(409) while other active addresses exist.

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

**Router prefix:** `/api/v1/register` — 13 endpoints, all deliberately unauthenticated (the
registration page has no JWT yet). `POST ""` always creates a `person`; it creates
`user_account(PENDING_APPROVAL)` + `registration_claim` **only when `has_membership` is true**
(a membership-less registrant gets no account — it could never log in — and the typed password is
discarded). Such a person can later submit a claim through `/lookup-existing` + `/claim`, verified
by `person_id` + date of birth. **No `sangha_sevi` is created until an admin approves the claim.**

**Local Sakha Number (GDR-009, Approved 2026-11-01 on the owner's instruction):** the request states explicitly whether the person was already a member before this system. `is_legacy_member=true` ⇒ `claimed_local_sakha_number` required (422 if blank/malformed); `false` (default) ⇒ it must be blank (422 if sent) and the number is auto-generated at approval. The attendance Sakha has its own pair `darshak_is_legacy_member` / `darshak_local_sakha_number`. One validator: `helpers.validate_claim_local_numbers()`. Applies to `POST ""` and `POST /claim`.

**Patra number (GDR-009 §2A) and Darshaka attendance (§2B):** `claimed_credential_document_number` follows the same `is_legacy_member` flag — legacy ⇒ required, strictly `<seq>/<yyyy>/<yyyy+1>` (e.g. `345/2026/2027`; 422 if malformed or years not consecutive; 409 if already issued); otherwise it must be blank (422 if sent) and is no longer required for a new Regular/Associate member. A new member's Anumati (Darshaka) or Parichaya (Regular/Associate) Patra number is auto-minted at approval. Validator `helpers.resolve_legacy_patra_number()`. A PROBATIONARY (Darshaka) registrant sending `is_attending_as_darshak` ⇒ 422 ("A Darshaka who attends another Sakha must transfer to it; use Sakha Transfer").

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
| 126a | GET | `/address-types` | `ADDRESS_TYPE` master data for the member address editor (login not required, same as the other lookups) |
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
| 80 | PATCH | `/{pk}` | Edit claim fields before decision; `is_legacy_member` / `darshak_is_legacy_member` are validated TOGETHER with the numbers (to turn legacy into new send `false` and `""` for both numbers in one request; `claimed_credential_document_number` is validated with the same flag; for a Darshaka claim the stored attendance Sakha is cleared and supplying one is 422) — the admin's verification step (GDR-009) |
| 81 | POST | `/{pk}/approve` | Approve — creates `sangha_sevi` + `membership_sakha_affiliation`, activates the account. Local Sakha Number per GDR-009: legacy claim lacking a number ⇒ 422; non-legacy ⇒ auto-generated (Regular/Associate or Darshak series). Patra credential: a legacy member's existing number recorded, otherwise minted (Anumati for a Darshaka, Parichaya — issue date pinned to the confirmed Dola Purnima — for Regular/Associate); a claim holding an attendance Sakha for a Darshaka ⇒ 422. Cross-Sakha attendance affiliation (Regular/Associate only): legacy number or next Darshak number at that Sakha; skipped only if an open affiliation exists there, any other collision ⇒ 409 and the approval rolls back. `ClaimListItem`/`ClaimDetailResponse` carry `is_legacy_member` (+ `darshak_is_legacy_member` on detail) |
| 82 | POST | `/{pk}/reject` | Reject the claim |

---

# 12. Tier 5 — Administration

**Router prefix:** `/api/v1/admin` — 32 endpoints (28 Tier 5 + 4 Tier 6 credential endpoints). Permission sets per endpoint are listed in
the last column (`any of`).

| # | Method | Path | Description | Permission (any of) |
|---|---|---|---|---|
| 83 | GET | `/users` | List users (search, sort, pagination); only accounts tied to an active `sangha_sevi` | `ADMIN_USER_VIEW`, `ADMIN_USER_MANAGE`, `MEMBERSHIP_APPROVE` |
| 84 | POST | `/users` | Create a user account (with `create_sangha_sevi=true` also creates the Sangha Sevi **and its home affiliation**; `is_legacy_member` (default false) + `local_sakha_erp_id`: legacy ⇒ number required; otherwise it must be blank and is auto-generated, never skipped; 422 on mismatch, 409 if taken — GDR-009; `credential_document_number` follows the same flag: legacy ⇒ required `<seq>/<yyyy>/<yyyy+1>` card number, otherwise blank — otherwise the Anumati/Parichaya number is minted; the response always carries `credential_type`/`credential_document_number`) | `ADMIN_USER_MANAGE`, `PERSON_MANAGE` |
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
| 101 | PATCH | `/organizations/{pk}` | Edit an org incl. `parent_organization_pk` re-parenting (a MAHILA_SANGHA moved under a Kendra is 422 when the central Mahila Sangha already exists); subtree-scoped (ADMIN-BR-076/077) | `ORGANIZATION_MANAGE`, `ORGANIZATION_VIEW` |
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
SOL-GOV-002/004) — 56 endpoints. Gates: `GOVERNANCE_VIEW` + `GOVERNANCE_MANAGE` are the two new
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
| GET | `/public/my-sakha-bodies` | Login | Read-only panel of the viewer's own Sakha-level governance bodies, for any logged-in member |
| GET | `/public/sakha-office-bearers` | Login | Per-Sakha President and Secretary (with mobile) for the Find-a-Sakha directory |
| GET | `/bodies/{body_master_pk}/assignments` | View | Member assignments of a body |
| GET | `/bodies/{body_master_pk}/allowed-positions` | View | Positions the body may hold, seat limit and seats filled |
| GET | `/bodies/{body_master_pk}/inherited-positions` | View | Read-only office-holders inherited from another body (empty for most types) |
| GET | `/advisory-board/missing-nominations` | View | Active Sakha Sanghas with no current Advisory Board MEMBER nomination (NSS-wide admins and the Advisory Board admin) |
| GET | `/advisory-board/dashboard` | View | One-read Advisory Board dashboard (roster, seats/vacancies, office bearers, acting cover, unrepresented Sakhas); NSS-wide admins and the Advisory Board admin |
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
| POST | `/acting-assignments/{acting_position_assignment_pk}/approve` | Login | The nominee named on an admin-initiated acting assignment approves it |
| POST | `/acting-assignments/{acting_position_assignment_pk}/reject` | Login | The nominee rejects it |
| GET | `/me/positions` | Login | Bodies on which the caller currently holds an office-bearer seat |
| POST | `/me/acting-delegations` | Login | Nominate another member of the same body to act on the caller's behalf |
| POST | `/me/acting-delegations/batch` | Login | Create several delegations at once |
| GET | `/me/acting-delegations` | Login | Delegations the caller has made |
| POST | `/me/acting-delegations/{acting_position_assignment_pk}/end` | Login | End a delegation the caller made |
| GET | `/me/pending-acting-approvals` | Login | Admin-initiated acting assignments awaiting the caller's own approval |
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

**Router prefix:** `/api/v1/correspondence` (`api/routers/correspondence.py`, SOL-ADMIN-009) — 19
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
| GET | `/{correspondence_pk}/history` | View | Status history / path tracker |
| POST | `/{correspondence_pk}/dispatch` | Manage | Mint the recipient organization's linked INWARD counterpart for an OUTWARD row addressed to an ORGANIZATION (scope checked against the sender's register only; 409 if already dispatched) |
| POST | `/broadcast` | Manage | One circular to every active descendant organization of a chosen type, each auto-dispatched (OUTWARD only) |
| POST | `/my-applications` | Login | Member "Send Application" (active Sangha Sevi required); may create a 2-step `correspondence_approval_step` chain (Sakha President, then Kendra office-bearer) |
| GET | `/my-applications` | Login | The caller's own submitted applications |
| GET | `/my-applications/{correspondence_pk}` | Login | One of the caller's own applications (404 otherwise) |
| GET | `/addressed-to-me` | Login | Applications currently addressed to the caller as `recipient_person_pk` |
| GET | `/approval-steps/pending-for-me` | Login | Approval-chain steps awaiting the caller's decision |
| POST | `/approval-steps/{step_pk}/decision` | Login | Decide step 1 (Sakha President) or step 2 (Kendra office-bearer) |
| GET | `/my-involvements` | Login | Every correspondence row the caller is attached to in any role |
| POST | `/{correspondence_pk}/transition` | Login + directed authority (recipient, or `CORRESPONDENCE_MANAGE` + scope) | Move to a new status per the §6.2 seven-row precondition table; reopening (ACTIONED/CLOSED → PENDING_ACTION) requires non-empty `remarks` (§6.3); always timestamped `NOW()` (§6.4) |
| POST | `/{correspondence_pk}/responsible-party` | Login + directed authority (recipient, or `CORRESPONDENCE_MANAGE` + scope) | Assign/clear the responsible person or organization (§5.4); permitted at any status, never itself a transition |
| POST | `/{correspondence_pk}/documents` | Manage | Associate a `document_master` row under a purpose (ORIGINAL/RESPONSE/ATTACHMENT/SUPPORTING); 201 |
| GET | `/{correspondence_pk}/documents` | View | List associated documents |
| POST | `/{correspondence_pk}/finance-references` | Manage | Reference a Finance transaction (201); `financial_transaction_pk` existence is not yet enforced — Finance (Tier 12) does not exist yet, documented gap |
| GET | `/{correspondence_pk}/finance-references` | View | List finance references |

**Status lifecycle (§6.1):** `REGISTERED → PENDING_ACTION → ACTIONED → CLOSED`, with
`ACTIONED`/`CLOSED → PENDING_ACTION` reopen paths and `REGISTERED → ACTIONED`/`CLOSED` direct
paths; no other transition pair is valid. `REGISTERED → PENDING_ACTION` additionally requires a
responsible person/organization already set on the row, and now also fires automatically when one is first assigned; `REGISTERED`/`PENDING_ACTION → ACTIONED` fires automatically when an in-register reply naming the row is created (see the Amendment blockquotes in `08_correspondence_register_business_rules.md`).

---

# 12e. Tier 6 — Attendance

**Router prefix:** `/api/v1/attendance` (`api/routers/attendance.py`) — 21 endpoints. Gates: `ATTENDANCE_VIEW` / `ATTENDANCE_MANAGE` (+ admin scope; the per-Sakha `NSS_ERP_ATTENDANCE_MARKER` role holds both for marking). Attendance Review actions and exception creation additionally call `_require_review_authority()` — the live Secretary/President seat on the member's home Sakha `SAKHA_GOVERNING_BODY` (President only for escalate-to-parichalak, reopen, override, and closing a review already ESCALATED_TO_PRESIDENT); `NSS_ERP_ADMIN` overrides.

| Method | Path | Gate | Description |
|---|---|---|---|
| POST | `/pujas` | Manage | Create a Weekly Sangha Puja (201; one per Sakha per date) |
| GET | `/pujas` | View | List pujas |
| POST | `/pujas/{weekly_sangha_puja_pk}/attendance` | Manage | Mark PRESENT/ABSENT/EXCUSED_ABSENCE for members (201); 3 consecutive ABSENT opens a review |
| GET | `/pujas/{weekly_sangha_puja_pk}/live` | View or Manage + scope | Live-register poll (see below) |
| PATCH | `/records/{attendance_pk}` | Manage | Correct a record (approving an Excused Absence needs review authority) |
| GET | `/records` | View | List attendance records |
| POST | `/exceptions` | View + review authority | Create an attendance exception (201) |
| GET | `/exceptions` | View | List exceptions |
| GET | `/reviews`, `/reviews/{review_pk}` | View | Review list / detail |
| POST | `/reviews/{review_pk}/close`, `/defer`, `/revisit`, `/escalate-to-president`, `/escalate-to-parichalak`, `/reopen`, `/override` | View + review authority | Review workflow actions |
| GET | `/watch-list` | View | Members with >= 2 (default) consecutive ABSENT, not yet at the 3-absence review trigger |
| GET | `/stats/organizations/{organization_pk}` | View | Organization attendance stats |
| GET | `/stats/organizations/{organization_pk}/members` | View | Per-member attendance within an organization |
| GET | `/stats/members/{sangha_sevi_pk}` | View | One member's attendance stats |

**Live register (several markers of one Sakha, 2026-10-31).** `AttendanceRecordResponse` (from `GET /records` and the mark response) additionally carries `marked_by_name`, `marked_by_sangha_sevi_id`, `marked_at` and `version` (`version` == `marked_at` == the row's last change, `GREATEST(created_at, COALESCE(updated_at, created_at))`).

`GET /pujas/{weekly_sangha_puja_pk}/live?since=<ISO-8601>` (`ATTENDANCE_VIEW` or `ATTENDANCE_MANAGE` + `require_org_in_scope` on the puja's Sakha; 404 unknown puja; 422 bad `since`). Response: `{"server_time", "marked_count", "changed": [{"sangha_sevi_pk", "attendance_pk", "attendance_status_code", "version", "marked_by_name", "marked_by_sangha_sevi_id", "marked_at", "is_active"}]}`. `changed` = rows whose version is newer than `since` minus a 1 s overlap (every row when `since` is omitted); `is_active=false` = unmarked/removed. `server_time` is the DB clock and is the next `since`. An `ETag` fingerprinting the puja's whole state is returned; `If-None-Match` with the current ETag answers `304` with no body.

`POST /pujas/{pk}/attendance` is backwards compatible. New optional request fields: per item `expected_version` (the `version` the marker last saw, echoed verbatim; `null` = "I saw it unmarked") and body `overwrite_sangha_sevi_pks: [uuid]`. If ANY item names `expected_version` the request is conflict-checked under a per-puja advisory lock + `SELECT ... FOR UPDATE`: a member conflicts when the row is active, its current version differs from `expected_version` AND its current status differs from the requested one (identical status is not a conflict; a soft-deleted row counts as unmarked) and the member is not in `overwrite_sangha_sevi_pks`. A member ALSO conflicts when the version matches but the row is active, was last changed by a DIFFERENT member than the caller, and has a different status than requested (changing someone else's mark needs an explicit overwrite; editing your own never conflicts; a row with no recorded marker is not attributable and is left alone; owner 2026-11-01). Any unconfirmed conflict saves NOTHING and returns `409` with `{"detail": {"message": str, "conflicts": [{"sangha_sevi_pk", "current_status_code", "changed_by_name", "changed_by_sangha_sevi_id", "changed_at", "requested_status_code"}]}}`. No `expected_version` anywhere = the original last-write-wins behaviour. ATT-006..010, the EXCUSED_ABSENCE re-mark authority check, consecutive-absence detection, audit and the not-before-puja-date rule are unchanged.

**Rate limit (fix 1, 2026-11-01):** this route is limited per signed-in user (`LIVE_ATTENDANCE_RATE_LIMIT`, default `120/minute`, key = JWT `sub`, client IP when there is no valid token — `api/rate_limit.py::user_or_ip_key`) and that limit REPLACES the global per-IP `RATE_LIMIT` for it, so members sharing one WiFi IP do not share a budget (2 s polling = 30 requests/min per open register). The page also polls adaptively (fix 2, 2026-11-02: 2 s while visible and active, 10 s after 60 s with no change, paused when hidden, 4/8/16/30 s back-off on errors; a 429's `Retry-After` raises the wait) — `LIVE_POLL` in `frontend/assets/js/attendance-register.js`.

Authority: `docs/03_Solution/modules/attendance/` (frozen 2026-10-27). Automated tests: `tests/api/test_attendance.py` and `tests/security/test_attendance_security.py` (261 collected; written but not yet run against the DB); UI tests in `tests/ui/test_ui_attendance.py` (132 collected), also never run.

---

# 12g. Live-refresh change feed

**Router prefix:** `/api/v1/live` (`api/routers/live.py`) — 1 endpoint, owner decision 2026-11-03 ("make data refresh automatically"). Read pool, no DDL.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/changes` | login only (`get_current_user`; no module permission) | Current `change_seq` of every watched table (marker table; no `since`) |

**Response** (`LiveChangesResponse`): `{"changed": [{"table_name": "...", "change_seq": 123}]}` - every table on the whitelist with the change number of its latest COMMITTED write (read from `nss.live_change_marker`). There is no `since`/cursor (an old client's `since` is ignored): the client keeps the last `change_seq` it saw per table and treats a different value as a change; its first reply is only the baseline. 401 without a valid token.

**What it discloses:** only THAT a table on the `LIVE_FEED_TABLES` whitelist (module constant in `live.py`, authoritative) changed — never record data or ids, and never a table outside the list (credential, session, counter, internal and ballot tables are excluded). The client then re-runs its own scoped loaders, so permissions and admin scope are untouched. The whitelist covers registration/claim and change-request approvals, Correspondence, Governance (bodies, assignments, acting cover, elections, nominations, results), the org-dashboard stats tables, Assets & Property and Sakha re-parent approvals (batch 1), plus (batch 2, 55 tables in all) users and roles (`user_account`, `user_role`, `admin_scope`, `role_master`), person/membership/family tables, reference and geography data, system settings and the festival calendar. `user_account` is on the list but its trigger ignores routine login bookkeeping columns, so a login never bumps its marker.

**Change numbers:** `change_seq` comes from the single global sequence `nss.live_change_seq`, assigned by a statement-level trigger (`fn_live_change_marker()`, `ddl/12_live_refresh/`) in the writing transaction, so it appears at commit and disappears on rollback; one multi-row statement is one bump; numbers can have gaps. Two commits to the SAME table are ordered by number (they queue on that table's marker row); numbers of different tables are not commit-ordered, which is why there is no global cursor.

**Rate limit:** per signed-in user (`LIVE_CHANGES_RATE_LIMIT`, default `60/minute`, key = JWT `sub`, client IP without a valid token — `api/rate_limit.py::user_or_ip_key`); replaces the global per-IP `RATE_LIMIT` for this route. The page polls every 5 s while active (12/min), 15 s when idle, paused while hidden (`LIVE_FEED` in `frontend/assets/js/live-refresh.js`).

Tests: `tests/api/test_live_changes.py`, `tests/security/test_live_security.py`, `tests/ui/test_ui_live_refresh.py` plus `tests/db/test_live_change_marker.py` (integration items not yet run against the project DB).

---

# 12f. Tier 6 — Sakha Re-parent Approvals

**Router prefix:** `/api/v1/org-reparent` (`api/routers/org_reparent.py`) — 4 endpoints, all login-only (`get_current_user`); visibility is the requester, assigned approvers, Kendra Governing Body members, and admins whose scope contains the Sakha (404 otherwise). Owner rule 2026-10-30: re-parenting a Sakha under a different Anchalika/Zilla (SAKHA_SANGHA or SAKHA_ASANA) is direct only for Kendra Governing Body members and the `NSS_ERP_ADMIN` super administrator (by role); everyone else files a request via `PATCH /admin/organizations/{pk}` (see below). Approval authority (deciding a step) is the LIVE office seat (substantive holder or active acting delegate) — no permission and no `NSS_ERP_ADMIN` override.

| Method | Path | Notes |
|---|---|---|
| GET | `` (root) | List visible requests. Filters: `mine`, `awaiting_my_decision`, `sakha_pk`, `request_status`, `page`, `page_size` (max 100) |
| GET | `/{request_pk}` | Request with steps; each step carries `viewer_can_decide`, the request `viewer_can_cancel` |
| POST | `/{request_pk}/steps/{step_pk}/decide` | `{decision: APPROVE\|REJECT, remarks}`; remarks required on REJECT; earlier steps must be APPROVED; requester can never decide own request. Final APPROVE re-validates and applies the parent change atomically (if re-validation fails the request is CANCELLED with a system remark) |
| POST | `/{request_pk}/cancel` | Requester, Kendra GB member or NSS_ERP_ADMIN, while PENDING |

**Chain (owner 2026-10-31):** Sakha President -> leaving (current) Anchalika/Zilla President -> destination Anchalika/Zilla President -> Kendra President (final); `step_role` is one of `SAKHA_PRESIDENT`, `SOURCE_PARENT_PRESIDENT`, `DEST_PARENT_PRESIDENT`, `KENDRA_PRESIDENT`. The leaving step does not exist when the Sakha's current parent is the Kendra. A step with no seated President, or whose seat the requester holds, is assigned to the Kendra President instead (`fallback_reason`); consecutive Kendra steps collapse into one. One open request per Sakha (409).

**`PATCH /admin/organizations/{pk}` change:** for a SAKHA_SANGHA/SAKHA_ASANA whose `parent_organization_pk` changes, a caller who is neither a Kendra GB member nor NSS_ERP_ADMIN gets **HTTP 202** with `{message, updated_fields, parent_change_applied: false, parent_change_pending_approval: true, reparent_request}`; all other fields in the same PATCH apply immediately, the parent is unchanged until the chain approves. A Kendra GB member or NSS_ERP_ADMIN gets 200 with `parent_change_applied: true` (and any open request for that Sakha is cancelled as superseded). Optional `parent_change_reason`. Other org types are unchanged.

Automated tests: `tests/api/test_org_reparent.py` (60 collected; chain matrix extended 2026-10-31) and `tests/ui/test_ui_org_reparent.py` (13 collected, source-parsing) — written but never run against a DB.

---

# 12g. Module #22 — Assets & Property

**Router prefix:** `/api/v1/assets-property` (`api/routers/assets_property.py`, schemas in `api/schemas/assets_property.py`) — 26 endpoints. Backend implemented 2026-11-02 (uncommitted; not yet run against the project DB); admin UI (`admin.html` Properties / Assets tabs, `assets-property.js`) added 2026-11-02, never opened in a browser. Design: `docs/03_Solution/modules/assets_property/` (SOL-AP-001..005); implementation decisions: GDR-010 (`Proposed`).

**Auth (every endpoint):** `Authorization: Bearer` JWT. Reads need `ASSET_VIEW` (or `ASSET_MANAGE`); writes need `ASSET_MANAGE`. In addition, **admin scope on the record's EFFECTIVE custodian organization** (`actor_scope_org_pks` / `require_org_in_scope`): a scope-bounded admin sees and manages only records whose effective custodian is an organization inside their scope subtree. *Effective custodian* (owner decision 2026-11-03, GDR-010 §2F) = the organization of the ACTIVE custodianship, or — for a **DISPOSED property / RETIRED asset only**, whose custody the terminal transition ENDed — the organization of its most recently ENDED custodianship (one SQL definition, `_effective_custodian_join()`, used by detail, list rows, every filter and every scope check; a disposed/retired record therefore stays visible to — and only to — the admins who could see it before, and never becomes custodian-less). A record with **no** effective custodian is visible/manageable only by the global authority (NSS_ERP_ADMIN / NSS-WIDE / KENDRA scope); 403 `This record has no custodian, so only NSS-wide administrators can <action>.` Roles (owner decisions 2026-11-02): ADMIN, KENDRA, SAKHA and PATHA_CHAKRA admins hold VIEW + MANAGE; ANCHALIKA and ZILLA admins, AUDITOR and REPORT_VIEWER hold VIEW only (an Anchalika/Zilla admin sees the physical organizations beneath them through the admin-scope subtree rule but every write is 403); the KENDRA_MAHILA_SANGHA admin, ATTENDANCE_MARKER, ADVISORY_BOARD admin and members hold neither (403). No member/public exposure. Errors: 401 no/invalid JWT; 403 missing permission or out of scope (`You can only <verb> this <property|asset> within your admin scope.`); 404 unknown/archived record; 409 conflict (second active custodian, live record archive, duplicate document link); 422 validation / invalid lifecycle transition / unknown master-data code (`Unknown PROPERTY_TYPE value 'X'.`).

**`{kind}`** in a path is the literal `properties` or `assets` (anything else is 422). **Controlled values travel as master_data `value_code` strings** (`*_code`), resolved server-side; the lists are admin-extendable, read them with `GET /foundation/master-data?category_code=…` (needs `FOUNDATION_VIEW`, which every role holding `ASSET_VIEW` also holds): `PROPERTY_TYPE` (LAND, BUILDING, PREMISES, OTHER_IMMOVABLE), `ASSET_TYPE` (EQUIPMENT, FURNITURE, INSTRUMENT, ARTICLE, OTHER_MOVABLE), `CUSTODIANSHIP_END_REASON` (TRANSFER, DISSOLUTION_VESTING, ORGANIZATIONAL_CHANGE, OTHER, DISPOSED, RETIRED — the last two are reserved for the terminal event, a transfer using them is 422), `STATUTORY_OBLIGATION_TYPE` (LAND_REVENUE, MUNICIPAL_TAX, LAND_RECORD, OTHER), `MAINTENANCE_TYPE` (REPAIR_MINOR, REPAIR_MAJOR, IMPROVEMENT, ADDITION, ALTERATION, UPKEEP, OTHER), `ASSET_PROPERTY_DOCUMENT_RELATIONSHIP` (TITLE_DEED, LAND_RECORD, MAINTENANCE_CERTIFICATE, PHOTOGRAPH, OTHER), `ACQUISITION_METHOD` (PURCHASE, DONATION, GIFT, BEQUEST, TRANSFER_IN, CONSTRUCTION, OTHER; the value lists were accepted as seeded by the owner, 2026-11-03). Lifecycle `status` values are fixed (not master data). All UUIDs are strings. Dates are `YYYY-MM-DD`; `effective_from` / `performed_at` / `custodian_effective_from` may not be in the future (422). No financial fields exist anywhere.

**Lifecycle (SOL-AP-003; also enforced by DB triggers).** Property: `REGISTERED → ACTIVE ⇄ UNDER_MAINTENANCE`, `ACTIVE|UNDER_MAINTENANCE → DISPOSED` (terminal). Asset: `REGISTERED → IN_CUSTODY ⇄ UNDER_MAINTENANCE`, `IN_CUSTODY|UNDER_MAINTENANCE → RETIRED` (terminal). REGISTERED advances to ACTIVE / IN_CUSTODY **automatically when the first custodian is assigned** (at registration or via `custodianships`); it cannot be advanced without a custodian. A custody transfer never changes status. Disposal/retirement is *recorded* here (the Governance approval reference goes in `remarks`, kept in the audit trail), never approved. **Disposal / retirement closes custody (owner decision 2026-11-03, GDR-010 §2F):** moving to DISPOSED / RETIRED ENDs the ACTIVE custodianship in the SAME transaction (`effective_to` = the transition date, end reason `DISPOSED` / `RETIRED`); the record keeps reporting that organization as its last custodian (`custodian_is_last`, below). A DISPOSED/RETIRED record accepts no further custody assignment/transfer (422, AP-046/047; also a DB trigger).

### Properties (`/properties`) and assets (`/assets`) — 6 endpoints each

| Method | Path | Auth | Request → Response |
|---|---|---|---|
| POST | `/properties` | `ASSET_MANAGE` + scope on `custodian_organization_pk` | Body `PropertyCreate`: `property_name` (req, ≤200), `property_type_code` (req), `location_description`, `holding_arrangement` (free text, recorded/legal holder — not the custodian), `notes` (each ≤2000, optional), `acquired_at` (date), `belongs_to_organization_pk` (uuid, optional; any ACTIVE organization — see "Belongs to" below), `acquisition_method_code` (optional ACQUISITION_METHOD code — see "Acquisition method" below), `custodian_organization_pk` (uuid; **required for scope-bounded admins**, optional only for NSS-wide admins → record starts REGISTERED with no custodian), `custodian_effective_from` (default today). → **201** `PropertyResponse` (`property_id` = `PROP<n>`, `status` ACTIVE when a custodian was given else REGISTERED). 403 foreign custodian org; 422 missing custodian (scoped admin) / unknown type / unknown org. |
| GET | `/properties` | `ASSET_VIEW` + scope | Query: `q` (name / id / location, case-insensitive substring), `type_code`, `status`, `custodian_organization_pk` (403 if outside scope), `include_sub_organizations` (bool, default false; with `custodian_organization_pk` matches that organization AND its whole subtree, still limited to the caller's scope; ignored without a custodian filter), `belongs_to_organization_pk` (uuid; only records attributed to that organization — ANDed with the custodian-scope clause, never widens visibility; no scope check on the value itself), `acquisition_method_code` (ACQUISITION_METHOD code; informational filter, ANDed with the scope clause), `page` (≥1, default 1), `page_size` (1–100, default 20). → `{items: PropertyResponse[], total, page, page_size}`; newest first; scope-bounded admins see only records whose effective custodian (active, or last for a DISPOSED/RETIRED record) is in scope. |
| GET | `/properties/{entity_pk}` | `ASSET_VIEW` + scope | → `PropertyResponse`: `property_pk, property_id, property_name, property_type_code, property_type_name, status, location_description, holding_arrangement, notes, acquired_at, current_custodianship_pk, current_custodian_organization_pk, current_custodian_organization_name, current_custodian_since, created_at, updated_at, belongs_to_organization_pk, belongs_to_organization_name` (both null when unset), `acquisition_method_code, acquisition_method_name` (null when unset), `custodian_is_last, custodian_ended_at` (see "Effective custodian fields" below). |
| PATCH | `/properties/{entity_pk}` | `ASSET_MANAGE` + scope | Body `PropertyUpdate` (any of `property_name`, `property_type_code`, `location_description`, `holding_arrangement`, `notes`, `acquired_at`, `belongs_to_organization_pk`, `acquisition_method_code`; only keys present are applied, `null` clears optional fields, name/type cannot be null; `status`/ids are ignored). Empty body → 422. → `PropertyResponse`. |
| POST | `/properties/{entity_pk}/transition` | `ASSET_MANAGE` + scope | Body `{status, remarks?}` (target status; `remarks` ≤2000, e.g. Governing Body decision reference). `DISPOSED` also ENDs the active custodianship in the same transaction (end reason `DISPOSED`). → `PropertyResponse`. 422 on unknown/invalid/terminal/same-status transition or REGISTERED without custodian. |
| DELETE | `/properties/{entity_pk}` | `ASSET_MANAGE` + scope | Soft-delete (archive); only while REGISTERED (registered in error) or DISPOSED; 409 for a live record. → `{message}`. Archived records 404 everywhere. |
| POST | `/assets` | as property | Body `AssetCreate`: `asset_name` (req), `asset_type_code` (req), `location_description`, `condition` (free text), `notes`, `acquired_at`, `belongs_to_organization_pk`, `acquisition_method_code`, `custodian_organization_pk`, `custodian_effective_from`. → **201** `AssetResponse` (`asset_id` = `AST<n>`, status IN_CUSTODY when a custodian was given). |
| GET | `/assets` | as property | Same filters (`type_code` = ASSET_TYPE code). → `{items: AssetResponse[], total, page, page_size}`. |
| GET | `/assets/{entity_pk}` | as property | → `AssetResponse`: `asset_pk, asset_id, asset_name, asset_type_code, asset_type_name, status, location_description, condition, notes, acquired_at, current_custodianship_pk, current_custodian_organization_pk, current_custodian_organization_name, current_custodian_since, created_at, updated_at, belongs_to_organization_pk, belongs_to_organization_name, acquisition_method_code, acquisition_method_name, custodian_is_last, custodian_ended_at`. |
| PATCH | `/assets/{entity_pk}` | as property | Body `AssetUpdate` (`asset_name`, `asset_type_code`, `location_description`, `condition`, `notes`, `acquired_at`, `belongs_to_organization_pk`, `acquisition_method_code`). → `AssetResponse`. |
| POST | `/assets/{entity_pk}/transition` | as property | Body `{status, remarks?}`. → `AssetResponse`. `RETIRED` also ENDs the active custodianship (see Lifecycle). |
| DELETE | `/assets/{entity_pk}` | as property | Archive while REGISTERED or RETIRED. → `{message}`. |

**"Belongs to" (owner-directed 2026-11-02, GDR-010 §2D).** `belongs_to_organization_pk` (nullable) on `POST`/`PATCH` of both kinds names the organization the property/asset belongs to when that differs from its physical custodian, e.g. an asset belonging to the Mahila Sangha but held under the supervision of the Kendra Sangha (custodian = Kendra, belongs to = Mahila Sangha). It is **informational only**: any organization type is allowed (Mahila incl. central, Kumari, Sevak, Paribarik, Zilla, Anchalika …), the only check is that the organization exists and is active (**422** `Belongs-to organization not found.`), there is no scope check on it and it never affects authorization, scope, the custodian rule, custodianship or the lifecycle; a custody transfer leaves it unchanged. `PATCH` with `null` clears it, omitting the key leaves it as is. Responses carry `belongs_to_organization_pk` and `belongs_to_organization_name`. Example: `POST /assets {"asset_name": "Harmonium", "asset_type_code": "INSTRUMENT", "custodian_organization_pk": "<Kendra>", "belongs_to_organization_pk": "<Mahila Sangha>"}`.

**Acquisition method (owner-directed 2026-11-03, GDR-010 §2E).** `acquisition_method_code` (optional) on `POST`/`PATCH` of both kinds records HOW the record was acquired (AP-023), from master-data category `ACQUISITION_METHOD` (PURCHASE and DONATION are grounded in the source documents; GIFT, BEQUEST, TRANSFER_IN, CONSTRUCTION, OTHER are candidates; admin-extendable). Unknown code → **422** `Unknown ACQUISITION_METHOD value '<code>'.`; `null` clears it on PATCH; omitting the key leaves it as is. **Informational only** — no effect on authorization, scope, the custodian rule or the lifecycle. Responses carry `acquisition_method_code` / `acquisition_method_name`; the list endpoints accept the filter `acquisition_method_code`.

**Effective custodian fields (owner decision 2026-11-03, GDR-010 §2F).** `current_custodianship_pk`, `current_custodian_organization_pk`, `current_custodian_organization_name` and `current_custodian_since` keep their names and carry the *effective* custodian (active, or — for a DISPOSED/RETIRED record — the last one). Two fields flag it: `custodian_is_last` (bool; `true` only on a DISPOSED/RETIRED record whose custodianship was ended by the terminal event, else `false`) and `custodian_ended_at` (date the custody ended, null while the custodian is active). A UI shows "Last custodian" plus a Disposed/Retired badge when `custodian_is_last`. The full history (including the ENDED row with end reason `DISPOSED`/`RETIRED`) stays in `GET …/custodianships`. The `custodian_organization_pk` / `include_sub_organizations` list filters match the effective custodian.

### Custodianship (`{kind}` = properties \| assets) — 3 endpoints

**Custodian type rule (owner rule 2026-11-02, GDR-010 §2C).** Property and assets are held only by PHYSICAL organizations: `SAKHA_SANGHA`, `SAKHA_ASANA`, `PATHA_CHAKRA`, `KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`. Naming any other organization (Anchalika/Zilla Sangha, Kumari/Sevak/Mahila/Paribarik wings, Advisory Board) as custodian — in `POST /properties`, `POST /assets`, `POST …/custodianships` or `POST …/custodianships/transfer` — returns **422** `<Custodian|New custodian> organization '<name>' is a <type name> (<TYPE_CODE>); property and assets are held by physical organizations (Sakha, Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira). Assign it to the Sakha or other physical organization instead.` The check precedes the scope check; the DB trigger `trg_custodianship_custodian_guard` is the backstop.


| Method | Path | Auth | Request → Response |
|---|---|---|---|
| GET | `/{kind}/{entity_pk}/custodianships` | `ASSET_VIEW` + scope | Full custody history, newest first. → `{items: CustodianshipResponse[], total}`; `CustodianshipResponse`: `custodianship_pk, property_pk, asset_pk` (one is null), `custodian_organization_pk, custodian_organization_name, status` (ACTIVE\|ENDED), `effective_from, effective_to, end_reason_code, end_reason_name, notes, created_at`. Exactly one ACTIVE row is the current custodian — except on a DISPOSED/RETIRED record, where nothing is ACTIVE and the newest ENDED row (end reason `DISPOSED`/`RETIRED`) is the last custodian. |
| POST | `/{kind}/{entity_pk}/custodianships` | `ASSET_MANAGE` + scope (⇒ NSS-wide only, since it targets a custodian-less record) | Assign the FIRST custodian. Body `{custodian_organization_pk, effective_from?, notes?}`. → **201** `CustodianshipResponse` (status ACTIVE); advances REGISTERED → ACTIVE/IN_CUSTODY. 409 if an ACTIVE custodian exists (use transfer); 422 for a DISPOSED/RETIRED record. |
| POST | `/{kind}/{entity_pk}/custodianships/transfer` | `ASSET_MANAGE` + scope over BOTH the current and the new custodian | Body `{new_custodian_organization_pk, end_reason_code? (default TRANSFER; use DISSOLUTION_VESTING for statutory vesting; DISPOSED/RETIRED are reserved → 422), effective_from? (default today; not future; not before the current custodianship began), notes?, location_description? (optional, updates the record's location in the same transaction)}`. Closes the current custodianship (ENDED, `effective_to`, end reason) and opens a new ACTIVE one; status unchanged. → **201** `{previous: CustodianshipResponse, current: CustodianshipResponse}`. 409 no current custodian; 422 same organization / terminal record / bad reason or date. After the transfer the record leaves the former custodian's scope. |

### Maintenance records — 4 endpoints

| Method | Path | Auth | Request → Response |
|---|---|---|---|
| GET | `/{kind}/{entity_pk}/maintenance-records` | `ASSET_VIEW` + scope | → `{items: MaintenanceResponse[], total}` (newest `performed_at` first). |
| POST | `/{kind}/{entity_pk}/maintenance-records` | `ASSET_MANAGE` + scope | Body `{maintenance_type_code (req), description?, performed_at?, notes?}`. → **201** `MaintenanceResponse`: `maintenance_record_pk, property_pk, asset_pk` (one null), `maintenance_type_code, maintenance_type_name, description, performed_at, notes, created_at`. Records what was done; no cost fields, no status change. |
| PATCH | `/maintenance-records/{record_pk}` | `ASSET_MANAGE` + scope (via the parent) | Body `{maintenance_type_code?, description?, performed_at?, notes?}` → `MaintenanceResponse`; the parent cannot change. |
| DELETE | `/maintenance-records/{record_pk}` | `ASSET_MANAGE` + scope | Soft-delete → `{message}`. |

### Statutory records — property only (AP-040), 4 endpoints (there is **no** asset route; `/assets/{pk}/statutory-records` is 404)

| Method | Path | Auth | Request → Response |
|---|---|---|---|
| GET | `/properties/{entity_pk}/statutory-records` | `ASSET_VIEW` + scope | → `{items: StatutoryRecordResponse[], total}`; `StatutoryRecordResponse`: `property_statutory_record_pk, property_pk, obligation_type_code, obligation_type_name, description, reference_number, notes, created_at`. |
| POST | `/properties/{entity_pk}/statutory-records` | `ASSET_MANAGE` + scope | Body `{obligation_type_code (req), description?, reference_number? (≤100), notes?}` → **201** `StatutoryRecordResponse`. Identifies the obligation only; payment is Finance's. |
| PATCH | `/statutory-records/{record_pk}` | `ASSET_MANAGE` + scope | Body `{obligation_type_code?, description?, reference_number?, notes?}` → `StatutoryRecordResponse`. |
| DELETE | `/statutory-records/{record_pk}` | `ASSET_MANAGE` + scope | Soft-delete → `{message}`. |

### Document links (Foundation `document_master`) — 3 endpoints

| Method | Path | Auth | Request → Response |
|---|---|---|---|
| GET | `/{kind}/{entity_pk}/documents` | `ASSET_VIEW` + scope | → `{items: DocumentLinkResponse[], total}`; `DocumentLinkResponse`: `link_pk, property_pk, asset_pk` (one null), `document_master_pk, document_type_code, document_name, document_number, relationship_type_code, relationship_type_name, notes, created_at`. |
| POST | `/{kind}/{entity_pk}/documents` | `ASSET_MANAGE` + scope | Body `{document_master_pk (req, must be an active document_master row), relationship_type_code?, notes?}` → **201** `DocumentLinkResponse`. 409 if already attached; 422 unknown document / relationship code. Files are not uploaded here — the document must already exist in the Foundation registry. |
| DELETE | `/{kind}/{entity_pk}/documents/{link_pk}` | `ASSET_MANAGE` + scope | Detach (soft-delete the link; the document stays) → `{message}`. The same document can be re-attached later. |

**Audit:** every write is recorded by the DB audit trigger (`system_event_log` + `field_change_log`, AP-071) and by `log_audit()` with `module = 'assets_property'` (actions `CREATE`, `UPDATE`, `DELETE`, `STATUS_CHANGE`, `TRANSFER`). Automated tests: `tests/db/test_assets_property_schema.py` (104 collected), `tests/api/test_assets_property.py` (81), `tests/security/test_assets_property_security.py` (208) — written but never run against the project DB.

---

# 13. Tier 5 — Audit

**Router prefix:** `/api/v1/audit` — 5 endpoints, `require_permission("AUDIT_VIEW")` (seeded to
`NSS_ERP_ADMIN`, `NSS_ERP_KENDRA_ADMIN`, `NSS_ERP_AUDITOR`), read-only pool.

| # | Method | Path | Filters | Description |
|---|---|---|---|---|
| 108 | GET | `/change-log` | `table_name`, `record_pk`, `field_name`, `changed_by_sangha_sevi_pk`, `changed_from`, `changed_to`, `limit`, `offset` | Paginated read of `nss.field_change_log` |
| 108a | GET | `/events` | `table_name`, `action`, `module`, `record_pk`, `actor_sangha_sevi_id`, `is_success`, `event_from`, `event_to`, `q`, `sort` (`asc`/`desc`), `limit`, `offset` | System event log explorer. Returns `{items, total, total_capped, event_from, limit, offset}`; without `event_from` and `record_pk` only the last 24 h are searched; `total` is exact up to 10,000 |
| 108b | GET | `/events/facets` | -- | Distinct `tables`, `actions`, `modules` of the last 30 days (filter dropdowns) |
| 108c | GET | `/events/{system_event_log_pk}` | -- | One event incl. its JSONB `detail`; 404 if unknown. Field-level rows of the same transaction: `/change-log` with `changed_from = changed_to = event_at` |
| 108d | GET | `/live-change-markers` | -- | Every `nss.live_change_marker` row (most recent `change_seq` first) with `on_live_whitelist`, plus `latest_change_seq`, `latest_table_name`, `whitelist_size`, `whitelist_without_marker`, `server_time` |

---

# 14. Frontend Routes

| Path | Description | HTML File |
|---|---|---|
| `/` | 302 redirect to `/login` | -- |
| `/login` | Login page | `login.html` |
| `/register` | Self-registration page | `register.html` |
| `/dashboard` | Member Dashboard (Personal, Membership, Family, Attendance, Governance, Documents tabs + an Org Dashboard for holders of an admin scope — tabs are built from the caller's role scopes) | `dashboard.html` |
| `/admin` | Administration console (Users, User Detail, Create User, Create Sangha-Sevi, Password, Create Organization, Organizations, Assign Sakhas, Registration Approvals, Geo Approvals, Person Directory, Member Directory, Organization Hierarchy, Org Dashboard, Reference Data, Geography, System Settings tabs; for `AUDIT_VIEW` holders the Audit & Diagnostics group: System Event Log `#auditEvents`, Live Change Markers `#liveMarkers`) | `admin.html` |
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
| 2 | Organization | 12 |
| 3 | Person | 9 (5 read + 3 address writes + 1 Aadhaar reveal, GDR-011) |
| 4 | Family | 16 (7 original read + 9 Tier 5) |
| 4 | Membership | 9 (8 + Tier 6 `/directory`) |
| 5 | Authentication | 10 |
| 5 | Registration | 13 |
| 5 | Claim Approval | 5 |
| 5 | Administration | 28 (+4 Tier 6 credential endpoints = 32) |
| 5 | Geo-Entry Approval | 4 |
| 5 | Audit | 5 |
| 6 | Governance | 56 |
| 6 | Membership Change Requests | 5 |
| 6 | Correspondence Register | 19 |
| 6 | Attendance | 20 |
| 6 | Sakha Re-parent Approvals | 4 |
| 6 | Assets & Property (Module #22) | 26 |
| 6 | Live-refresh change feed | 1 |
| **Total** | | **284** |

(per-router, decorator-counted: admin 32, assets_property 26, attendance 21, audit 5, auth 10, bootstrap 4, claim_approval 5, correspondence 19, family 16, foundation 33, geo_approval 4, governance 56, live 1, membership 9, membership_change_request 5, org_reparent 4, organization 12, person 9, registration 13.)

The endpoint numbers in the tables above are stable identifiers, not path order: #1-#46 are the
original Tier 0-4 set; #47-#137 were appended as Tier 5 endpoints landed. Tier 6 endpoints (sections 8b, 12c and the `T6` admin rows) are not numbered.

---

# End of Document
