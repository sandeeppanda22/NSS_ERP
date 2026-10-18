# api/

FastAPI application — the only web/API layer in the codebase. Implements **Tier 0**
(read-only bootstrap-RBAC, unauthenticated), **Tier 1** (Foundation), **Tier 2** (
Organization), **Tier 3** (Person), and **Tier 4** (Family + Membership) —
no ORM — behind a cross-tier security middleware stack (headers, opt-in CORS, rate limiting,
plus a new Content-Security-Policy) and a shared error-handler layer (`error_handlers.py`).
15 routers (201 endpoints; Tier 6 adds `governance.py` 46 + `membership_change_request.py` 5 + `correspondence.py` 9, admin 28→32); the endpoint inventory and per-router counts live in
`docs/03_Solution/api/API_CONTRACT.md`.
**Partway through this branch's development, Tiers 1-3
and Membership (Tier 4) gained authenticated gating** — they were read-only/no-auth through
the Tier 4 release. Foundation, Organization, `person.py`'s list/search, and `membership.py`'s
list/search/darshak-summary use a blanket `require_permission("<MODULE>_VIEW")`; `person.py`'s
two per-person endpoints and `membership.py`'s per-member endpoints use an ownership model
(`get_current_user` + `require_self_or_permission()`: the holder of the permission, or the
person/member themself). **Family (Tier 4) took a different path**: rather than a blanket
permission, every one of `family.py`'s 16
endpoints (7 original reads + 9 Tier 5 writes) now requires `get_current_user` plus an
ownership check — a person reaches their own family through their `family_relationship`/
`family_admin` row, with `FAMILY_VIEW`/`FAMILY_MANAGE` as the admin override (see the Family
section below). Only Tier 0's 4 `bootstrap.py` endpoints remain fully unauthenticated now
(plus `registration.py`'s public endpoints, `POST /auth/login`/`refresh`/`forgot-password`/
`reset-password`, which are unauthenticated by nature).

**Tier 5 (Authentication + Administration + Audit) is released in v0.11.0** (merged to `main`). It adds the first
authenticated, write-path endpoints: JWT login/refresh/logout/password-management
(`routers/auth.py`), user/role/organization administration (`routers/admin.py`),
self-registration (`routers/registration.py`), Sakha-admin claim approval
(`routers/claim_approval.py`), and an authenticated audit-trail viewer (`routers/audit.py`),
backed by a new `api/dependencies/` layer and two new
`api/services/` modules (`auth_service.py`, `rbac_service.py`) — see "Endpoints (Tier 5)" below
and `docs/PROJECT_DOCUMENTATION.md` → Architecture ("Tier 5") for full detail. 
An earlier Django prototype lived under `backend/` and covered parts of Foundation,
Authentication, Family, Membership, and Heritage; it was fully archived and removed once the
FastAPI direction (`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md`) was adopted.
`backend/` is now empty.

## Layout

```
api/
├── main.py             FastAPI app entry point — builds `app`, registers the security
│                        middleware (in code order: `SlowAPIMiddleware` rate limiting → opt-in
│                        CORS → `add_security_headers`; Starlette runs the last-registered one
│                        outermost, so security headers wrap everything — CSP is emitted by that
│                        same security-headers middleware, not a separate layer), registers the
│                        `error_handlers.py` handlers (validation / `psycopg2.IntegrityError` /
│                        catch-all), includes all 15 routers (the six Tier 0-4 ones plus, Tier 5,
│                        `auth`/`admin`/`registration`/`claim_approval`/`audit`/`geo_approval`, then Tier 6
│                        `governance`/`membership_change_request`/`correspondence`),
│                        mounts `frontend/assets/` at `/assets`. A `lifespan` hook logs a
│                        startup warning for each insecure dev setting left on (`DEBUG_MODE`,
│                        `CSP_ENABLED=false`, `CSP_REPORT_ONLY`) and closes both DB pools on
│                        shutdown. **The six original Tier 0-4 page
│                        routes (`/`→`index.html`, `/foundation`, `/organization`, `/person`,
│                        `/family`, `/membership`) have been deleted** (see the "Retired
│                        standalone verification pages" comment in the file) — root `/` now
│                        302-redirects to `/login` instead. Serves — Tier 5,
│                        in progress — `frontend/login.html` at `/login`,
│                        `frontend/dashboard.html` at `/dashboard`, `frontend/admin.html` at
│                        `/admin`, `frontend/register.html` at `/register` (each gated
│                        `if <page>_path.is_file()`). There is no `/forgot-password`
│                        page route — that flow is inline on `/login`. There is no
│                        `/claim-approval` route or `claim-approval.html` file — that feature
│                        shipped as a tab inside `admin.html` instead. **Every page route
│                        serves through `_serve_page()`/`_render_html_with_asset_versions()`**
│                        (v0.11.0) instead of a bare `FileResponse` — rewrites
│                        each served page's `/assets/js|css/*` references to
│                        `?v=<10-char sha256 prefix of current file contents>`, computed per
│                        request but memoized by file mtime, replacing the old hand-maintained
│                        `?v=N` convention (removed from every HTML page); the HTML response
│                        itself is `Cache-Control: no-store`
├── config.py            `Settings` singleton (`settings`), read from api/.env via python-dotenv.
│                        Required: DB_NAME/DB_USER/DB_PASSWORD (`validate()`); optional DB_HOST
│                        (default localhost), DB_PORT (5432), API_PORT (8001 — read but not
│                        used anywhere in `api/`; the port comes from the uvicorn command line),
│                        DISABLE_DOCS, CORS_ORIGINS (comma-separated, default empty),
│                        RATE_LIMIT (default `60/minute`), DEBUG_MODE, pool sizes
│                        DB_READ_POOL_MIN/MAX (2/15) and DB_WRITE_POOL_MIN/MAX (1/5), and the
│                        Content-Security-Policy knobs CSP_ENABLED (default true),
│                        CSP_REPORT_ONLY (default false), CSP_SCRIPT_SRC_EXTRA/
│                        CSP_STYLE_SRC_EXTRA (comma-separated extra origins). Tier 5 (in
│                        progress): DB_WRITE_USER/DB_WRITE_PASSWORD, JWT_SECRET_KEY (no default),
│                        JWT_ACCESS_TOKEN_MINUTES (30)/JWT_REFRESH_TOKEN_DAYS (7)/
│                        JWT_ABSOLUTE_SESSION_DAYS (30), plus hardcoded (non-env) constants:
│                        JWT_ALGORITHM `HS256`, lockout (5 failed attempts / 30 s), password
│                        policy (8-128 chars, 365-day expiry, 30-day warning) and forgot-password
│                        OTP (6 digits, 15-minute expiry, max 3 active OTPs per user, 60-minute
│                        rate window). `Settings.validate_auth()` (JWT_SECRET_KEY +
│                        DB_WRITE_USER/PASSWORD) is called only when the write pool is first
│                        created
├── database.py          psycopg2 `ThreadedConnectionPool`s. Read pool (`get_pool()`/
│                        `get_connection()`, `nss_db_backend`, SELECT-only, 2-15 conns by
│                        default) — `get_connection()` is a FastAPI generator dependency. Tier 5
│                        (in progress): write pool (`get_write_pool()`/`get_write_connection()`,
│                        `nss_db_writer`, 1-5 conns by default) — commits on success, rolls
│                        back on exception. Also `close_pool()` (closes both) and
│                        `check_connection()` (backs `/bootstrap/health`)
├── error_handlers.py    Three app-wide handlers registered in `main.py`, so every failure reaches
│                        the browser as a readable `detail` string instead of a bare status code:
│                        `validation_exception_handler` (flattens Pydantic's error list into
│                        one sentence per field via `humanize_field()`),
│                        `integrity_error_handler` (`psycopg2.IntegrityError` — duplicate
│                        key → 409; FK/NOT NULL/CHECK → 422; readable instead of an unhandled 500), and
│                        `unhandled_exception_handler` (catch-all 500 with a generic detail; logs
│                        the real error). An endpoint's own `HTTPException` still wins. Covered
│                        by `tests/api/test_error_messages.py`
├── helpers.py           Shared cursor→Pydantic conversion (`rows_to_models`, `row_to_model`) used
│                        by every router, plus pagination constants (`DEFAULT_LIMIT = 100`,
│                        `MAX_LIMIT = 500`) and list-sorting helpers (`SORT_ASC`/`SORT_DESC`,
│                        `natural_sort_key()`, `build_order_by()` — whitelist-based ORDER BY so
│                        `sort_by`/`sort_dir` query params never reach SQL unvalidated).
│                        Tier 5 write-path helpers:
│                        ID minting — `next_id()` (atomic `id_sequence_master` `UPDATE ...
│                        RETURNING`, returns `prefix + current_value`; ignores the table's
│                        `padding_length`), `peek_next_id()` (preview without consuming),
│                        `financial_year_bounds()`, `next_credential_document_number()`
│                        (Kendra/Anumati `<seq>/<fy_start>/<fy_end>` counter via
│                        `credential_sequence_counter`); membership —
│                        `compose_local_sakha_erp_id()`, `insert_sakha_affiliation()`,
│                        `issue_membership_credential()`, `is_probationary_membership_type()`,
│                        `require_sakha_organization()`, `resolve_scoped_sakha()`,
│                        `resolve_kumari_sevak_parent_sakha()`, `get_kendra_organization_pk()`;
│                        Tier 6 additions — `next_sakha_local_number()` (atomic Local Sakha
│                        number per `(organization, REGULAR|DARSHAK)` namespace via
│                        `sakha_local_number_counter`, no financial-year reset, MBR-030C/048),
│                        `close_sakha_affiliation()` (sets `effective_to` + `ARCHIVED`; the
│                        counterpart to `insert_sakha_affiliation()`, which now takes an optional
│                        `local_number` and a `source_event_type` of ENROLLMENT/TRANSFER/
│                        REACTIVATION), `log_patra_history()` (single writer for
│                        `parichaya_patra_history`/`anumati_patra_history`),
│                        `set_membership_credential_status()` (retire a Patra to EXPIRED/
│                        CANCELLED/REPLACED and log the history row; used by the Darshaka to
│                        Regular promotion);
│                        lookups/get-or-create — `get_system_setting()`,
│                        `resolve_or_create_city_village()`, `resolve_or_create_postal_code()`,
│                        `get_active_status_pk()`; guards — `require_entity()` (404 on a missing/
│                        inactive row), `require_self_or_permission()` (shared ownership check
│                        behind `person.py`/`membership.py`), `check_duplicate_contact()`;
│                        passwords — `record_password_history()`,
│                        `validate_and_hash_password()`; audit — `log_audit()` (writes a row to
│                        `nss.system_event_log` — see Audit trail below). **Also 5 shared SQL
│                        fragment constants**, each spliced (via an f-string) into 2+ routers'
│                        queries rather than copy-pasted: `FAMILY_MAJORITY_CTE_SQL` (the FAM-036
│                        majority-rule CTE, shared by `organization.py`'s `/children-stats` +
│                        `/stats` and `family.py`'s `_FAMILY_SELECT`),
│                        `ORGANIZATION_ADDRESS_JOINS_SQL` (shared by `organization.py`'s
│                        `_ORG_SELECT` and `admin.py`'s org-list query),
│                        `PERSON_MASTER_DATA_JOINS_SQL` (gender/marital-status/blood-group
│                        triple, shared by `person.py`'s DETAIL/SUMMARY/COUNT selects),
│                        `MEMBER_JOINS_SQL` (shared by `membership.py`'s SELECT/COUNT), and
│                        `USER_ACCOUNT_MEMBERSHIP_JOINS_SQL` (`admin.py`'s user-list/detail
│                        membership + pending-claim joins). Plus constants
│                        `DARSHAK_LOCAL_ID_MARKER_SETTING`,
│                        `PROBATIONARY_MEMBERSHIP_TYPE_CODE`
├── middleware.py        `add_security_headers(request, call_next)` — sets
│                        `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`/
│                        `Permissions-Policy` on every response, plus `Cache-Control: no-store`
│                        on `/api/*` and `public, max-age=86400, must-revalidate` on `/assets/*`.
│                        Also emits the `Content-Security-Policy` assembled by `build_csp()` (or
│                        the `-Report-Only` variant when CSP_REPORT_ONLY is set; nothing when
│                        CSP_ENABLED is false), skipping `CSP_EXEMPT_PATHS` — `/docs`, `/redoc`,
│                        `/openapi.json` — because Swagger UI embeds an inline script
├── routers/             15 routers; module docstrings of `foundation.py`,
│   │                    `membership.py`, `person.py`, `admin.py`, `auth.py`, `registration.py`
│   │                    and `family.py` still describe their original/partial endpoint set — see
│   │                    "Known gaps" at the bottom of this file
│   ├── bootstrap.py     4 endpoints under /api/v1/bootstrap — no auth, no ORM, raw
│   │                    parameterized SQL against nss.role_master/permission_master/
│   │                    role_permission
│   ├── foundation.py    33 endpoints under /api/v1/foundation — 21 reads
│   │                    (master data, system config, geography, runtime document metadata,
│   │                    see below) plus 8 admin write endpoints (`POST`/`PATCH` on
│   │                    `/master-data`, `/settings`, `/sequences`, `/festival-calendar-dates`) and 4
│   │                    member `propose` POSTs (`get_current_user` only). Reads gated by
│   │                    `require_permission("FOUNDATION_VIEW")`, writes by
│   │                    `require_permission("FOUNDATION_MANAGE")` (festival-calendar writes:
│   │                    `FOUNDATION_CALENDAR_MANAGE`, NSS_ERP_ADMIN only) in Tier 5. Also
│   │                    exports `fetch_countries()`/`fetch_states()`/`fetch_districts()`/
│   │                    `fetch_postal_codes()`/`fetch_master_data()`, reused by `registration.py`
│   ├── organization.py  11 endpoints under /api/v1/organization across 3 tables — reference
│   │                    data (types, statuses), core organizations (list/detail/children — the
│   │                    list query is a shared `fetch_organizations()` function, also called by
│   │                    `registration.py`'s public reference-data endpoints), children-stats
│   │                    (recursive, no depth-cap guard — see Known gaps), `/organizations/{pk}/stats`
│   │                    (same recursive counts collapsed to one row of whole-subtree totals for
│   │                    the requested org, 403s outside the caller's own admin scope via
│   │                    `require_org_in_scope`, backs the Org Dashboard tab), and a
│   │                    self-referencing hierarchy tree via `WITH RECURSIVE` (depth guard at 10).
│   │                    `/organizations/{pk}/wings` + `/wings/{wing_type_code}/members`
│   │                    (wing-body summary/roster). All gated by `require_permission("ORGANIZATION_VIEW")`
│   │                    except `/organizations/selectable` (member-facing dropdown lookup;
│   │                    `get_current_user` only)
│   ├── person.py        5 endpoints under /api/v1/person across 2 tables — person list
│   │                    (with gender/marital-status/blood-group filters + pagination) and
│   │                    trigram-based (`pg_trgm`) search, both gated by
│   │                    `require_permission("PERSON_VIEW")`; `/search-selectable` (same search,
│   │                    `get_current_user` only, for the family-head add-member picker); person detail and person addresses
│   │                    use an ownership model instead (`get_current_user` +
│   │                    `require_self_or_permission()` — `PERSON_VIEW` holder or the person
│   │                    themself)
│   ├── family.py        16 endpoints under /api/v1/family across 6 tables — 7 original reads
│   │                    (family group list/detail/members/head-history, plus `/graph` (dynamic
│   │                    relationship-label BFS via `api/services/family_graph.py`),
│   │                    `/sakha-alignment` (FAM-036 majority-rule computation), and
│   │                    `/person/{pk}/membership-summary`) plus 9 Tier 5 endpoints
│   │                    (`GET /person/{pk}/families`, create family, add/remove member, create
│   │                    link, list/assign/revoke admin, transfer-head). **Unlike the routers
│   │                    above, `family.py` uses an
│   │                    ownership model instead of a blanket `require_permission` gate: every
│   │                    one of the 16 endpoints requires `get_current_user` (only `GET /families`
│   │                    requires `FAMILY_VIEW` outright), and a person
│   │                    reaches their own family through their `family_relationship`/
│   │                    `family_admin` row, with `FAMILY_VIEW`/`FAMILY_MANAGE` as the admin
│   │                    override** — a deliberate design choice per the router's own module
│   │                    docstring, not a gap. `tests/api/test_family_ownership.py` (20 tests)
│   │                    covers the ownership path for the write endpoints plus `/graph`;
│   │                    `/person/{pk}/membership-summary` still has no coverage
│   ├── membership.py    8 endpoints under /api/v1/membership — member list, search and
│   │                    `/organizations/{pk}/darshak-summary` (per-org Darshak counts for the
│   │                    Org Dashboard tab) gated by `require_permission("MEMBERSHIP_VIEW")`;
│   │                    member detail, Sakha affiliations, Parichaya Patra, Anumati Patra and
│   │                    journey events use an ownership model instead (`get_current_user` plus
│   │                    either `MEMBERSHIP_VIEW` or being the member themself, via a shared
│   │                    `_require_member_view()` → `require_self_or_permission()`). Tier 6:
│   │                    `/search` takes an optional `organization_pk` (subtree-aware on
│   │                    `sangha_sevi.organization_pk`) so governance nominee/voter pickers only
│   │                    offer members from a body's own subtree
│   ├── auth.py          Tier 5 — 10 endpoints under /api/v1/auth: login, refresh,
│   │                    logout, sessions (list), sessions/{pk} (revoke), change-password, forgot-password, reset-password, /me, /profile
│   ├── admin.py         Tier 5/6 — 32 endpoints under /api/v1/admin: user list/
│   │                    create/detail/check-account, reset-password/status/delete; role
│   │                    assignment; `POST /persons` + `GET /persons/check-contact` + `GET`/`PATCH /persons/{pk}` (profile-details correction) + `PATCH /patra/{patra_type}/{patra_pk}/document-number` (MBR-030H); Sangha Sevi
│   │                    provisioning (create, check, check-batch, without-account); organization
│   │                    list/create/PATCH/short-code plus 5 creation-helper GETs
│   │                    (`kumari-sevak-sakha-options`, `sakha-scope-options`,
│   │                    `code-availability`, `next-code`); `dashboard-stats`; Tier 6: 4 member-credential endpoints under
│   │                    `/credentials/members` (health list, `/{sangha_sevi_pk}/timeline`, `/issue`,
│   │                    `/promote`). `GET /users/{pk}` also returns read-only `auto_granted_scopes`
│   │                    (§63). `PATCH /organizations/{pk}` also accepts `parent_organization_pk`
│   │                    (re-parenting, backs the "Assign Sakhas" admin tab). Module-level
│   │                    `_ALLOWED_PARENT_TYPES`/`_NO_ADDRESS_TYPES`/`_SAKHA_GATED_TYPES`
│   │                    constants are shared by create/update rather than re-defined per function
│   ├── registration.py  Tier 5 — 12 endpoints under /api/v1/register: `POST ""`
│   │                    self-registration (account + claim only when `has_membership`),
│   │                    `POST /check-duplicate`, `POST /lookup-existing` + `POST /claim` (the
│   │                    "previously registered" flow: person_id + DOB, then account + claim), plus 8 public,
│   │                    unauthenticated reference-data endpoints (`/reference-data`, `/countries`,
│   │                    `/states`, `/districts`, `/cities`, `/postal-codes`, `/post-offices`, `/sakhas`) that thinly wrap `foundation.py`'s/
│   │                    `organization.py`'s own shared query functions — fixes a regression where
│   │                    Tier 5's permission gating had silently emptied every dropdown on the
│   │                    public registration page
│   ├── claim_approval.py Tier 5 — 5 endpoints under /api/v1/admin/claims:
│   │                        Sakha-admin review queue for registration_claim rows. Its frontend
│   │                        shipped as a "Registration Approvals" tab inside
│   │                        `admin.html`/`admin.js`, not a standalone page
│   ├── geo_approval.py   Tier 5 — 4 endpoints under /api/v1/admin/geo-entries: review queue for
│   │                     member-proposed district/postal-code/post-office/city-village rows
│   │                     (list, detail, approve, correct), `FOUNDATION_MANAGE` + admin scope
│   ├── governance.py     Tier 6 — 46 endpoints under /api/v1/governance: body-type/position
│   │                     catalogues, bodies, member + acting assignments (incl. forced-removal
│   │                     request/approve/reject), elections, nominations, votes (officer-recorded,
│   │                     self-service, reset), tally, results and result apply, plus two
│   │                     any-login public panels. `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`, admin scope
│   ├── correspondence.py Tier 6 — 9 endpoints under /api/v1/correspondence: register,
│   │                     list (scoped), detail, status transition (§6.2), responsible-party,
│   │                     document and finance-reference sub-resources; `CORRESPONDENCE_VIEW`/
│   │                     `CORRESPONDENCE_MANAGE` + admin scope on `register_organization_pk`;
│   │                     reference numbers via `helpers.next_correspondence_reference_number()`
│   ├── membership_change_request.py Tier 6 — 5 endpoints under
│   │                     /api/v1/membership/change-requests: Sakha Transfer / Apply for Darshak
│   │                     two-step release/accept workflow (MBR-048/049); write-pool counterpart to
│   │                     the read-only `membership.py`
│   └── audit.py          Tier 5 — 1 endpoint under /api/v1/audit: `GET /change-log`,
│                          a filterable/paginated view over `nss.field_change_log` (one row per
│                          field per CREATE/UPDATE/DELETE, with actor and timestamp), gated by
│                          `AUDIT_VIEW`; the authenticated counterpart to Tier 1's
│                          deliberately-unexposed audit data
├── dependencies/        Tier 5 — FastAPI `Depends()` factories, distinct from
│   │                    `services/`. No `__init__` exports; import from the submodules
│   ├── auth.py          `get_current_user()` (mandatory HTTP Bearer JWT auth: access token only,
│   │                    loads `UserContext`) / `get_optional_user()` (same, returns None instead
│   │                    of 401ing) / `get_write_connection()` (the `nss_db_writer` connection
│   │                    dependency used by every write endpoint — resolves the caller via
│   │                    `get_optional_user()` and sets the `nss.actor_user_account_pk`/
│   │                    `nss.actor_sangha_sevi_pk` session variables the DB `fn_audit_trigger()`
│   │                    reads, on the *write* connection the trigger actually runs on)
│   └── rbac.py          `require_permission(code)` / `require_any_permission(*codes)` —
│                        wrap `get_current_user()` and additionally 403 on missing permission
├── services/
│   ├── family_graph.py  BFS graph-traversal relationship computation over `nss.family_link`
│   │                    edges (`FamilyGraph`, `PersonNode`, `build_family_graph()`, a
│   │                    `PATH_LABELS` kinship lookup) — first file in this layer, distinct from
│   │                    routers/schemas; exercised only indirectly via `/graph` in
│   │                    `tests/api/test_family_ownership.py` (no unit tests of its own)
│   ├── auth_service.py  Tier 5 — Argon2 `hash_password()`/`verify_password()`,
│   │                    `create_access_token()`/`create_refresh_token()`/`decode_token()`
│   │                    (defaults: access 30 min / refresh 7 days / 30-day absolute session max,
│   │                    all three `JWT_*` env-configurable; `decode_token()` enforces the
│   │                    absolute max), `validate_password_policy()` (8-128 chars, >=1 uppercase,
│   │                    >=1 digit), `is_account_locked()`/`calculate_lockout_until()` (5
│   │                    attempts / 30 s)
│   └── rbac_service.py  Tier 5 — `UserContext`/`ScopeInfo` dataclasses +
│                        `load_user_context()`: permissions = union of every active role's
│                        `role_permission` rows; scopes = one per active `user_role` +
│                        `admin_scope`. `UserContext.is_super_admin()` is true only for the
│                        `NSS_ERP_ADMIN` role (the sole blanket authority; every other role is
│                        scope-bounded). Scope-check helpers: `actor_scope_org_pks()`,
│                        `org_in_scope()`, `require_org_in_scope()`, `require_person_in_scope()`,
│                        `require_account_in_scope()`.
│                        Tier 6: `ScopeInfo.user_role_pk` may now be `None`, and
│                        `load_composite_grants(cur, person_pk)` (public) returns the §63 composite
│                        auto-grant scopes + permissions derived live from governance positions
│                        (substantive plus acting holders); `load_user_context()` merges them in
└── schemas/
    ├── bootstrap.py      Pydantic response models (RoleResponse, PermissionResponse,
    │                     HealthResponse) — audit columns deliberately excluded
    ├── foundation.py     Response models, one per exposed table/view (CategoryResponse,
    │                     MasterDataResponse, SettingResponse, SequenceResponse, CountryResponse,
    │                     StateResponse, DistrictResponse, CityVillageResponse,
    │                     PostalCodeResponse, PostalCodeMappingResponse, DocumentResponse) plus
    │                     Create/Update request models for master-data/settings/sequences — audit
    │                     columns, `current_value`, and unimplemented FK columns deliberately
    │                     excluded
    ├── organization.py   OrganizationTypeResponse, StatusResponse, OrganizationResponse,
    │                     OrgChildStatsResponse, OrgStatsResponse,
    │                     OrganizationHierarchyNodeResponse — OrganizationResponse includes
    │                     contact/online-presence fields (phone_number, mobile_number, email,
    │                     org_email, website_url, org_website_url, youtube_channel_url,
    │                     org_youtube_channel_url)
    ├── person.py         PersonResponse, PersonSummaryResponse, PersonAddressResponse,
    │                     PersonListResponse — PersonResponse/PersonSummaryResponse never
    │                     include `aadhaar_encrypted`/`aadhaar_hash`, only `aadhaar_last4` for
    │                     masked display (PER-BR-081); audit columns excluded
    ├── family.py         8 original Pydantic models (FamilyGroupResponse, FamilyMemberResponse,
    │                     FamilyGraphMemberResponse, PersonMembershipSummaryResponse,
    │                     FamilyHeadHistoryResponse, SakhaAffiliationCount, MemberSakhaInfo,
    │                     FamilySakhaAlignmentResponse) plus 8 more (Tier 5) for the
    │                     write endpoints: AddFamilyMemberRequest,
    │                     RemoveFamilyMemberRequest, CreateFamilyLinkRequest,
    │                     CreateFamilyRequest, FamilyAdminResponse, AssignFamilyAdminRequest,
    │                     RevokeFamilyAdminRequest, TransferHeadRequest
    ├── membership.py     MemberResponse, SakhaAffiliationResponse, ParichayaPatraResponse,
    │                     AnumatiPatraResponse, JourneyEventResponse, MemberListResponse,
    │                     OrgDarshakSummaryResponse
    ├── auth.py           Tier 5 — LoginRequest/Response,
    │                     RefreshRequest/Response, ChangePasswordRequest,
    │                     ForgotPasswordRequest/Response, ResetPasswordRequest, MeResponse,
    │                     ScopeResponse, MessageResponse, UpdateProfileRequest
    ├── admin.py          Tier 5 — CreateUserRequest, ResetPasswordRequest,
    │                     UpdateStatusRequest, AssignRoleRequest, CreateSanghaSeviRequest,
    │                     UserAccountResponse, UserListResponse, UserDetailResponse,
    │                     RoleAssignmentResponse, CreateSanghaSeviResponse,
    │                     AccountlessSanghaSeviResponse/ListResponse, `AutoGrantedScopeResponse` (Tier 6, §63) (organization-create/update
    │                     and other request bodies are defined inline in `routers/admin.py`)
    ├── governance.py     Tier 6 — Create/Update request + response models for body types,
    │                     positions, bodies, assignments (incl. removal requests), acting
    │                     assignments, elections, nominations, votes (`CastVoteRequest`,
    │                     `SelfCastVoteRequest`, `ResetBallotsRequest`), tally, results
    ├── correspondence.py Tier 6 — CorrespondenceCreate/Response/ListResponse,
    │                     StatusTransitionRequest, ResponsiblePartyAssignRequest,
    │                     DocumentAssociation*, FinanceReference*
    ├── membership_change_request.py Tier 6 — ChangeRequestCreate, SourceDecisionRequest,
    │                     DestinationDecisionRequest, ChangeRequestResponse/ListResponse
    └── audit.py          Tier 5 — FieldChangeLogResponse (the one schema in this
                          codebase that deliberately includes audit-actor columns, since the
                          whole point of this endpoint is exposing them)
```

## Endpoints (Tier 5 — released in v0.11.0)

Not yet merged/released. Requires `api/.env` to also carry `DB_WRITE_USER`, `DB_WRITE_PASSWORD`,
and `JWT_SECRET_KEY` (see `docs/PROJECT_DOCUMENTATION.md` → Configuration). Endpoints that
mutate data (and `POST /auth/login`, which records failed attempts/lockout) use the `nss_db_writer`
pool via `api/dependencies/auth.py::get_write_connection` (wraps `api/database.py::get_write_connection` and sets the `nss.actor_*` audit variables); pure reads — `POST /auth/refresh`, `GET /auth/me`,
every `GET` under `/admin` and `/admin/claims`, `GET /audit/change-log`, and the `/register` `GET`s
— use the read-only `nss_db_backend` pool (`get_connection`). Permission codes below are the
exact `require_permission`/`require_any_permission` arguments in each router.

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| POST | `/api/v1/auth/login` | none | Access + refresh JWT; login_id = Sangha Sevi ID or Person ID |
| POST | `/api/v1/auth/refresh` | refresh token (body) | New access JWT (refresh token is not rotated) |
| POST | `/api/v1/auth/logout` | access token | Revokes the caller's `user_session` row (Tier 5 A4); client discards tokens |
| GET | `/api/v1/auth/sessions` | access token | Own active sessions (`is_current` flags the caller's) |
| DELETE | `/api/v1/auth/sessions/{session_pk}` | access token | Revoke one of own sessions; generic 404 otherwise |
| POST | `/api/v1/auth/change-password` | access token | Self-service password change (policy + reuse check) |
| POST | `/api/v1/auth/forgot-password` | none | Generates a 6-digit OTP (`password_reset_token`); always returns a generic message (anti-enumeration); `otp_debug` only when `DEBUG_MODE`. **The OTP is not delivered** — email/SMS sending is a `TODO` in `auth.py` |
| POST | `/api/v1/auth/reset-password` | none | Consumes the OTP, sets a new password |
| GET | `/api/v1/auth/me` | access token | Profile + permissions + scopes |
| PATCH | `/api/v1/auth/profile` | access token | Self-service update of `mobile_number`/`country_phone_code`/`email`/`date_of_birth`; name fields are admin-only |
| GET | `/api/v1/admin/users` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | List user accounts tied to an active `sangha_sevi` (scope-filtered unless NSS-WIDE) |
| POST | `/api/v1/admin/users` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Create a user account |
| GET | `/api/v1/admin/users/check-account/{person_pk}` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Whether a person already has a usable or soft-deleted login (Create User wizard) |
| GET | `/api/v1/admin/users/{pk}` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | User detail + role assignments |
| POST | `/api/v1/admin/users/{pk}/reset-password` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Admin-initiated password reset |
| PATCH | `/api/v1/admin/users/{pk}/status` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Activate/suspend/deactivate; only touches `account_status` (never creates a `sangha_sevi`) — activating a `PENDING_APPROVAL` user 422s if a PENDING claim exists (use Registration Approvals) or the person has no active `sangha_sevi` |
| DELETE | `/api/v1/admin/users/{pk}` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Soft-delete (also revokes roles + scopes) |
| GET | `/api/v1/admin/users/{pk}/roles` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | List role assignments |
| POST | `/api/v1/admin/users/{pk}/roles` | `ADMIN_ROLE_MANAGE` | Assign role + scope |
| DELETE | `/api/v1/admin/users/{pk}/roles/{user_role_pk}` | `ADMIN_ROLE_MANAGE` | Revoke a role assignment |
| POST | `/api/v1/admin/persons` | `PERSON_MANAGE` | Admin creates a person directly (no account) |
| GET | `/api/v1/admin/persons/check-contact` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Advisory duplicate lookup by mobile/email |
| POST | `/api/v1/admin/sangha-sevi` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Create a standalone Sangha Sevi record, decoupled from user-account creation; scope-checked |
| GET | `/api/v1/admin/sangha-sevi/check/{person_pk}` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | Whether a person already has an active Sangha Sevi record |
| POST | `/api/v1/admin/sangha-sevi/check-batch` | same | Batch check up to 100 persons for an active Sangha Sevi or a pending registration claim |
| GET | `/api/v1/admin/sangha-sevi/without-account` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | Paginated, searchable Sangha Sevis with an SS ID but no usable login (Create Account picker) |
| GET | `/api/v1/admin/organizations` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | List organizations (scope-filtered) |
| POST | `/api/v1/admin/organizations` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE`, then in-handler: `NSS_ERP_ADMIN` only, except `KUMARI_SANGHA`/`SEVAK_SANGHA` (also the target Sakha's own admin, ORG-BR-101/102) | Create an organization |
| GET | `/api/v1/admin/organizations/kumari-sevak-sakha-options` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE` | Sakha choices for creating a Kumari/Sevak wing (ORG-BR-101/102) |
| GET | `/api/v1/admin/organizations/code-availability` | same | Live duplicate check for an `organization_code` or `short_code` (`field`/`value`/`exclude_pk` query params) |
| GET | `/api/v1/admin/organizations/next-code` | same | Sequence-driven organization-code preview |
| GET | `/api/v1/admin/sakha-scope-options` | same | Sakha options for member-scoped records (ORG-BR-103) |
| PATCH | `/api/v1/admin/organizations/{pk}/short-code` | any of `ORGANIZATION_MANAGE`/`ORGANIZATION_VIEW`, then subtree scope check (`NSS_ERP_ADMIN`/NSS-WIDE: any org) | Set/clear the 3-5 char short code |
| PATCH | `/api/v1/admin/organizations/{pk}` | same | Update org contact/address/jurisdiction fields and `parent_organization_pk` (re-parenting, validated against `_ALLOWED_PARENT_TYPES`) |
| GET | `/api/v1/admin/dashboard-stats` | any of `ADMIN_USER_VIEW`/`ADMIN_USER_MANAGE`/`MEMBERSHIP_APPROVE` | Aggregated counts for the admin dashboard cards, scoped to the viewer's own scope |
| GET | `/api/v1/admin/persons/{pk}` | any of `ADMIN_USER_MANAGE`/`PERSON_MANAGE`, person in scope | Raw editable profile fields for the admin Profile Details card |
| PATCH | `/api/v1/admin/persons/{pk}` | same | Admin correction of personal-info fields |
| PATCH | `/api/v1/admin/patra/{patra_type}/{patra_pk}/document-number` | any of `MEMBERSHIP_MANAGE`/`ADMIN_USER_MANAGE`, Patra's Sakha in scope | Correct an issued Parichaya/Anumati Patra number (audit-logged) |
| GET | `/api/v1/admin/geo-entries/{entity}` | `FOUNDATION_MANAGE`, scoped | List member-proposed geographic entries (`entity` = `district`/`postal-code`/`post-office`/`city-village`; `status` default `PENDING`) |
| GET | `/api/v1/admin/geo-entries/{entity}/{entry_pk}` | same | Entry detail |
| POST | `/api/v1/admin/geo-entries/{entity}/{entry_pk}/approve` | same | PENDING to APPROVED |
| POST | `/api/v1/admin/geo-entries/{entity}/{entry_pk}/correct` | same | Find-or-create canonical row, mark CORRECTED, re-point `person_address` FKs |
| POST | `/api/v1/register` | none | Self-registration — creates `person` + `user_account(PENDING_APPROVAL)` + optional `registration_claim` |
| POST | `/api/v1/register/check-duplicate` | none | JSON body `{mobile_number, country_phone_code, email}` → `{mobile_exists, email_exists}` pre-submit check |
| GET | `/api/v1/register/reference-data` | none | Countries + gender/marital-status/blood-group/membership-type master-data + the Sakha list, bundled into one call for the public registration page |
| GET | `/api/v1/register/countries`/`/states`/`/districts`/`/cities`/`/postal-codes`/`/post-offices`/`/sakhas` | none | Public location-cascade and Sakha lookups, thin wrappers over `foundation.py`'s `fetch_*()` functions and `organization.py`'s `fetch_organizations()` |
| GET | `/api/v1/admin/claims` | any of `MEMBERSHIP_APPROVE`/`ADMIN_USER_MANAGE`, scoped | List registration claims (`claim_status` filter, default `PENDING`; `page`/`page_size` pagination) |
| GET/PATCH | `/api/v1/admin/claims/{pk}` | same | Claim detail / admin edits before approval |
| POST | `/api/v1/admin/claims/{pk}/approve` | same | Creates `sangha_sevi` + affiliation (+ mandatory credential for a new Sangha Sevi), activates the account |
| POST | `/api/v1/admin/claims/{pk}/reject` | same | Leaves the account `PENDING_APPROVAL`, remarks required |
| GET | `/api/v1/audit/change-log` | `AUDIT_VIEW` | Filterable, paginated `nss.field_change_log` history — the authenticated counterpart to Tier 1's deliberately-unexposed `/api/v1/foundation/change-log` (which doesn't exist) |

**`nss.permission_master`/`nss.role_permission` are now seeded** (`database/seed/00_bootstrap/
01_permission_master.sql`/`03_role_permission.sql`) — `FOUNDATION_VIEW`/`ORGANIZATION_VIEW`/
`PERSON_VIEW`/`PERSON_VIEW_SENSITIVE`/`FAMILY_VIEW`/`MEMBERSHIP_VIEW`/`AUDIT_VIEW` plus the
admin/user-management permission set are mapped to roles, so `require_permission(...)`/
`require_any_permission(...)` calls above no longer blanket-403 for every role. No test coverage
gap list has been separately tracked for Tier 5 yet — see `tests/README.md`.

See `docs/PROJECT_DOCUMENTATION.md` → Key Workflow #9 for the full registration → approval →
login → RBAC flow this layer implements.

## Endpoints (Tier 6 — Governance, uncommitted on `feature/tier6-governance`)

All write endpoints use the auditing `api/dependencies/auth.py::get_write_connection`; reads use
`get_connection`. "View" = `require_any_permission("GOVERNANCE_VIEW","GOVERNANCE_MANAGE")`,
"Manage" = `require_permission("GOVERNANCE_MANAGE")`, "Login" = `get_current_user` only. A body or
election with `organization_pk IS NULL` is NSS-wide and manageable only by `NSS_ERP_ADMIN`/NSS-WIDE;
org-scoped ones go through the subtree scope check (ADMIN-BR-076/077).

**`/api/v1/governance`** (`routers/governance.py`, 46 endpoints; paths relative to the prefix)

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| GET | `/bodies/sakha-scope-options` | Manage | Parent-Sakha picker for Sakha-anchored bodies (scoped; must precede `/bodies/{body_master_pk}`) |
| GET | `/me/parichalak-status` | Login | Whether the caller holds the NSS-wide Parichalak seat (GOV-BR-043-A) |
| GET/POST | `/body-types` | View / Manage | Body-type catalogue / create |
| PATCH/DELETE | `/body-types/{body_type_master_pk}` | Manage | Update / soft-deactivate |
| GET/POST | `/positions` | View / Manage | Position catalogue / create |
| PATCH/DELETE | `/positions/{position_master_pk}` | Manage | Update / soft-deactivate |
| GET | `/bodies`, `/bodies/{body_master_pk}` | View | Body list / detail |
| POST | `/bodies` | Manage | Create a body |
| PATCH/DELETE | `/bodies/{body_master_pk}` | Manage | Update / soft-deactivate |
| GET | `/public/national-bodies` | Login | Kendra GB, Advisory Board, central Mahila Parichalana Mandali and the viewer's own Sakha GB with current composition |
| GET | `/public/sakha-office-bearers` | Login | Per-Sakha President and Secretary (with mobile) for the Find-a-Sakha directory |
| GET | `/bodies/{body_master_pk}/assignments` | View | Member assignments |
| GET | `/bodies/{body_master_pk}/allowed-positions` | View | Allowed positions, seat limit, seats filled |
| GET | `/bodies/{body_master_pk}/inherited-positions` | View | Read-only holders inherited from another body |
| GET | `/advisory-board/missing-nominations` | View | Active Sakhas with no current Advisory Board MEMBER nomination (NSS-wide admins only) |
| GET | `/mukhya-pujaka` | View | The NSS-wide Mukhya Pujaka seat and current holder |
| POST | `/bodies/{body_master_pk}/assignments` | Manage | Assign a member (composition, singleton, membership and seat-limit checks) |
| POST | `/assignments/{body_member_assignment_pk}/end` | Manage | End an assignment |
| POST | `/assignments/{body_member_assignment_pk}/resign` | Login | Voluntary self-withdrawal; only the person on the assignment (no override); `RESIGNED` |
| POST | `/assignments/{body_member_assignment_pk}/request-removal` | Manage | Forced-removal request for a Sakha-nominated seat (super-admin only; `PENDING_REMOVAL`) |
| POST | `/assignments/{body_member_assignment_pk}/approve-removal`, `/reject-removal` | Manage | Decision by the body's own sitting President |
| GET/POST | `/bodies/{body_master_pk}/acting-assignments` | View / Manage | Acting assignments / create |
| POST | `/acting-assignments/{acting_position_assignment_pk}/end` | Manage | End an acting assignment |
| GET | `/elections` | View | Election list |
| GET | `/elections/open-for-voting` | Login | Elections in VOTING this member may vote in (must stay registered before `/elections/{election_pk}`) |
| GET | `/elections/{election_pk}` | View | Election detail |
| POST | `/elections` | Manage | Create an election |
| PATCH | `/elections/{election_pk}/status` | Manage | Advance election status |
| GET/POST | `/elections/{election_pk}/nominations` | View / Manage | Nominations / file one |
| PATCH | `/nominations/{election_nomination_pk}/status` | Manage | Accept/reject a nomination |
| POST | `/elections/{election_pk}/votes` | Manage | Officer-recorded vote |
| POST | `/elections/{election_pk}/votes/self` | Login | Member's own ballot (voter from session; GOV-BR-043/045) |
| POST | `/elections/{election_pk}/votes/reset` | Manage | Hard-delete cast ballots (President unilateral, or admin with recorded President approval) |
| GET | `/elections/{election_pk}/tally` | View | Tally |
| GET/POST | `/elections/{election_pk}/results` | View / Manage | Results / declare one |
| POST | `/results/{election_result_pk}/apply` | Manage | Hand a declared winner into a live `body_member_assignment` |

**`/api/v1/membership/change-requests`** (`routers/membership_change_request.py`, 5 endpoints)

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| POST | `` | `get_current_user`; self, or `MEMBERSHIP_MANAGE` for another member | File a `TRANSFER` or `DARSHAK` request (201) |
| GET | `` | `get_current_user`; `MEMBERSHIP_VIEW`/`MEMBERSHIP_APPROVE` = scoped admin view, else own rows only | Paginated list (`status`, `organization_pk`, `page`, `page_size`) |
| GET | `/{change_request_pk}` | `get_current_user` | Detail |
| POST | `/{change_request_pk}/source-decision` | `MEMBERSHIP_APPROVE` + old Sakha in scope | `RELEASE`/`REJECT` while `PENDING_SOURCE_RELEASE` |
| POST | `/{change_request_pk}/destination-decision` | `MEMBERSHIP_APPROVE` + new Sakha in scope | `ACCEPT`/`REJECT` while `PENDING_DESTINATION_ACCEPT`; auto-numbered via `next_sakha_local_number()` unless `is_legacy_import` + `new_local_number` |

**`/api/v1/admin/credentials/members`** (`routers/admin.py`, 4 endpoints)

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| GET | `` | any of `MEMBERSHIP_VIEW`/`MEMBERSHIP_MANAGE`/`ADMIN_USER_MANAGE`, scoped | Per-member credential health OK/EXPIRING/LAPSED/MISSING (`state`, `membership_type`, `search`, `page`, `page_size`) |
| GET | `/{sangha_sevi_pk}/timeline` | same | Full Anumati + Parichaya history |
| POST | `/{sangha_sevi_pk}/issue` | any of `MEMBERSHIP_MANAGE`/`ADMIN_USER_MANAGE` | Issue/renew the expected credential, optional manual number (MBR-030H) |
| POST | `/{sangha_sevi_pk}/promote` | same | Darshaka to Regular: expire Anumati, issue Parichaya (MBR-010) |

**§63 composite auto-grant:** `rbac_service.load_composite_grants()` derives admin scopes live
from governance positions (no stored rows): Kendra GB members -> `NSS_ERP_KENDRA_ADMIN`;
Advisory Board President/Secretary -> `NSS_ERP_ADVISORY_BOARD_ADMIN`; Sakha GB, Sevak Sangha
Executive, Anchalika/Zilla/Patha Chakra GB President/Secretary -> the matching org-scoped admin
role; Mahila Parichalana Mandali President/Joint Secretary -> `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`
(central) or `NSS_ERP_SAKHA_ADMIN` (per Sakha). Acting holders are added only when not already
covered. `GET /api/v1/membership/search` also accepts an optional `organization_pk` (subtree-aware).

## Audit trail (v0.11.0)

Every Tier 5 write endpoint calls `api/helpers.py::log_audit()` after each mutation, inserting a
row into the new `nss.system_event_log` table (`action`, `table_name`, `record_pk`, `actor_pk`,
`actor_user_account_pk`, `module`, `summary`, `detail` JSONB, `is_success`) —
`database/ddl/01_foundation/14_system_event_log.sql`. Independently, `database/ddl/01_foundation/
15_audit_trigger.sql` attaches a `fn_audit_trigger()` `AFTER INSERT OR UPDATE OR DELETE` trigger
to every `nss.*` table except `system_event_log`/`field_change_log` (a `DO $$` loop over
`pg_tables`; attached after Phase 13, so admin-bootstrap and seed rows are unaudited), so raw SQL
writes are captured even if application code forgets to call `log_audit()`. The trigger writes
**both** logs: one row-level event to `system_event_log` plus one field-level row per changed
field to `nss.field_change_log` (`07_field_change_log.sql`; `created_at`/`updated_at` and the
`id_sequence_master`/`credential_sequence_counter` tables are excluded from the field log). A
single mutation can therefore produce two `system_event_log` rows (one app-authored with a
human `summary`, one trigger-authored and generic) — accepted, since `log_audit()` also carries
semantic actions (LOGIN/APPROVE). The actor comes from the `nss.actor_*` variables set by
`api/dependencies/auth.py::get_write_connection()`.

## Security middleware

Registered in `api/main.py`. Starlette runs the **last-registered** middleware outermost, so
the effective request order is security headers → CORS → rate limiting → route:

1. **Rate limiting** (`slowapi`) — `Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])`
   registered via `SlowAPIMiddleware`; default `60/minute` per client IP, global (no per-route
   `@limiter.limit` overrides exist anywhere in `api/`). Returns 429 once the limit trips.
   `POST /auth/forgot-password`'s 3-per-hour cap is a separate, DB-backed check on
   `password_reset_token`, not this limiter.
2. **CORS** (`fastapi.middleware.cors.CORSMiddleware`) — only added `if settings.CORS_ORIGINS:`;
   empty by default, so no CORS headers appear on any response out of the box. When configured,
   `GET`/`POST`/`PATCH`/`DELETE` are allowed, all request headers, credentials allowed, never a
   wildcard origin.
3. **Security headers** (`api/middleware.py`, `app.middleware("http")`) — always on:
   `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
   `Referrer-Policy: strict-origin-when-cross-origin`,
   `Permissions-Policy: camera=(), microphone=(), geolocation=()` on every response, plus
   `Cache-Control: no-store` on `/api/*` responses, and `Cache-Control: public, max-age=86400,
   must-revalidate` on `/assets/*` responses. **Content-Security-Policy** (`build_csp()`) is
   enabled and enforcing by default (`default-src 'self'`; `script-src 'self' 'unsafe-eval'
   https://cdn.jsdelivr.net` + `CSP_SCRIPT_SRC_EXTRA` — no `'unsafe-inline'`; `style-src 'self'
   'unsafe-inline'` + `CSP_STYLE_SRC_EXTRA`; `img-src 'self' data:`; `frame-ancestors 'none'`;
   `object-src 'none'`), switchable to `-Report-Only` via `CSP_REPORT_ONLY`, off via
   `CSP_ENABLED=false`, and skipped for `/docs`, `/redoc`, `/openapi.json`. Deliberately skips
   `X-XSS-Protection` (obsolete) and HSTS (left to Render's edge TLS).
4. **Error handlers** (`api/error_handlers.py`, registered via `app.add_exception_handler`) —
   validation, `psycopg2.IntegrityError`, and catch-all, each returning a plain-string `detail`.

Verified by `tests/security/test_security_headers.py` (24 tests) and
`tests/api/test_error_messages.py` (15) — the old flat `tests/test_security.py` no longer exists
(see `CLAUDE.md` → Tests & lint). Full walkthrough:
`docs/03_Solution/code_explanations/SECURITY_CODE_EXPLANATIONS.md`.

## Running

From the **repository root** (not from `api/`):

```
python3 -m uvicorn api.main:app --reload --port 8001   # macOS/Linux
py -m uvicorn api.main:app --reload --port 8001         # Windows
```

Requires `api/.env` with `DB_NAME`, `DB_USER`, `DB_PASSWORD` (required — `Settings.validate()`
raises without them) plus `DB_HOST`/`DB_PORT` (defaults `localhost`/`5432`); Tier 5 endpoints also
need `DB_WRITE_USER`, `DB_WRITE_PASSWORD`, `JWT_SECRET_KEY` (see the `config.py` entry above for
every optional variable, and `database/scripts/README.md` for the full bootstrap-to-running-API
sequence — `database/scripts/06_setup_env.sh` generates a working `.env`). The database must be
built and `nss_db_backend` granted read access (done by `02_build`'s Phase 9, or
`database/scripts/04_grant_backend.sql`) before this will connect to anything meaningful.

Swagger UI: `http://localhost:8001/docs` (set `DISABLE_DOCS=true` in `api/.env` to turn off
`/docs`, `/redoc`, and `/openapi.json`).

## Endpoints (Tier 0)

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/bootstrap/health` | `{"status", "database"}` — liveness/DB-connectivity probe |
| GET | `/api/v1/bootstrap/roles` | The 10 frozen roles from `nss.role_master` |
| GET | `/api/v1/bootstrap/permissions` | `nss.permission_master` rows — was empty by design through Tier 4; **now returns real rows in Tier 5**, since the catalogue is seeded |
| GET | `/api/v1/bootstrap/roles/{role_pk}/permissions` | Permissions mapped to a role — same, no longer empty for roles with real `role_permission` mappings; 404 if `role_pk` doesn't match an active role |

All four are unauthenticated and read-only — they exist to verify the RBAC schema is queryable,
not to enforce RBAC.

## Endpoints (Tier 1)

33 endpoints under `/api/v1/foundation` — no ORM, raw
parameterized SQL. 21 reads **gated by `require_permission("FOUNDATION_VIEW")` on the Tier 5
branch** (read-only/no-auth through Tier 4); 8 admin write endpoints (below) gated by
`require_permission("FOUNDATION_MANAGE")` (festival-calendar writes: `FOUNDATION_CALENDAR_MANAGE`) instead, plus 4 member `propose` endpoints gated by `get_current_user` only. Grouped by theme:

| Group | Endpoints |
|-------|-----------|
| Master data | `/categories`, `/categories/{pk}`, `/master-data` (filter by `category_code`/`category_pk`; `GET`+`POST`), `/master-data/{pk}` (`GET`+`PATCH`) |
| System config | `/settings` (`GET`+`POST`), `/settings/{setting_key}` (`GET`+`PATCH`), `/sequences` (`GET`+`POST`, excludes `current_value`), `/sequences/{sequence_code}` (`PATCH`) |
| Geographic | `/countries`, `/countries/{pk}`, `/states`, `/states/{pk}`, `/districts`, `/districts/{pk}`, `/cities`, `/postal-codes`, `/post-offices` (`postal_code_pk` required), `/postal-code-mappings`, `/sakha-postal-codes` |
| Runtime | `/documents` |
| Member-assisted entry | `POST /districts/propose`, `/postal-codes/propose`, `/post-offices/propose`, `/city-villages/propose` — a member (active Sangha Sevi required, else 403) submits an unseen value as `entry_status='PENDING'`; reviewed via `/api/v1/admin/geo-entries/*` |
| Festival calendar | `/festivals`, `/festival-calendar-dates` (`GET`+`POST`), `/festival-calendar-dates/{pk}` (`PATCH`) |

The 8 `POST`/`PATCH` endpoints above are new (v0.11.0) —
`create_master_data`/`update_master_data`, `create_setting`/`update_setting`,
`create_sequence`/`update_sequence`, `create_festival_calendar_date`/`update_festival_calendar_date` — each writes via `get_write_connection` and logs through
`log_audit()`.

`nss.field_change_log` is deliberately not exposed here — it is reachable only through the
`AUDIT_VIEW`-gated `GET /api/v1/audit/change-log` (Tier 5, see above). All list
endpoints filter `is_active = TRUE` (except the postal-code-mapping junction table, which has no
such column); detail endpoints 404 on missing/inactive rows. (`foundation.py`'s own module
docstring still says "17 GET endpoints ... No authentication" — stale.) Full contract:
`docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`. Verified by pytest integration
tests (`tests/api/test_foundation.py`, `tests/api/test_geo_approval.py`; some of the original 59 were extracted into
`tests/security/`).

## Endpoints (Tier 2)

11 endpoints under `/api/v1/organization` (table below lists the original 8; `/organizations/selectable`, `/organizations/{pk}/wings`, `/organizations/{pk}/wings/{wing_type_code}/members` are documented in API_CONTRACT.md) — no ORM,
parameterized SQL. **Gated by `require_permission("ORGANIZATION_VIEW")` in Tier 5**
(read-only/no-auth through Tier 4). Organization type values come from Foundation `master_data`
(category `ORGANIZATION_TYPE`). Status values come from the unified ERP-wide
`STATUS` category. Organization LEFT JOINs
Foundation's geography tables (country, state, district, city_village, postal_code)
for address resolution, since those FKs are nullable.

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/organization/types` | The 13 frozen organization types from `nss.master_data` (category `ORGANIZATION_TYPE`) |
| GET | `/api/v1/organization/statuses` | The 7 Organization-applicable statuses out of the unified `STATUS` category's 16 total values from `nss.master_data` |
| GET | `/api/v1/organization/organizations` | Organizations with resolved type/status/parent/geography context; optional `type_code`/`status_code` filters, `limit`/`offset` pagination (default 100, max 500) |
| GET | `/api/v1/organization/organizations/{organization_pk}` | Single organization detail; 404 if missing/inactive |
| GET | `/api/v1/organization/organizations/{organization_pk}/children` | Direct children of an organization; 404 if the parent `organization_pk` doesn't exist |
| GET | `/api/v1/organization/organizations/{organization_pk}/children-stats` | Aggregate family/member/person counts per direct child, recursing through descendant Sakhas and applying the FAM-036 majority-rule "effective Sakha" computation; its own recursive CTE has **no** depth-cap guard, unlike `/hierarchy` |
| GET | `/api/v1/organization/organizations/{organization_pk}/stats` | New, released in v0.11.0 — same recursive counts collapsed to one row of whole-subtree totals for the requested org itself; 403s outside the caller's own admin scope (ADMIN-BR-076); backs the new Org Dashboard tab |
| GET | `/api/v1/organization/hierarchy` | Full organization tree as a flat list with a `depth` field, via a `WITH RECURSIVE` CTE (depth guard at 10); `limit`/`offset` pagination |

All list endpoints filter `is_active = TRUE`; detail/children endpoints 404 on a missing parent.
Full contract: `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` (documents the original 7,
not yet updated for `/stats`). Verified by 67 pytest
integration tests (`tests/api/test_organization.py`; some of the original 72 were extracted into
`tests/security/`, and 4 more new ones cover `/stats` via
`tests/security/test_organization_stats_security.py` instead).

## Endpoints (Tier 3)

5 endpoints under `/api/v1/person` (plus `/search-selectable`, see API_CONTRACT.md) — no ORM, raw parameterized SQL. **Gated on the Tier 5
branch** (read-only/no-auth through Tier 4): `/persons` and `/search` by
`require_permission("PERSON_VIEW")`; `/persons/{person_pk}` and
`/persons/{person_pk}/addresses` by `get_current_user` + `require_self_or_permission()` (a
`PERSON_VIEW` holder, or the person themself).
Gender,
marital status, blood group, emergency relationship, and address type are resolved via JOINs
against Foundation's `master_data`. Trigram search relies on `pg_trgm` (installed in
`database/scripts/01_extensions.sql`).

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/person/persons` | Active persons (compact summary — no Aadhaar/emergency/photo fields); optional `gender_code`/`marital_status_code`/`blood_group_code` filters, `limit`/`offset` pagination (default 100, max 500) |
| GET | `/api/v1/person/persons/{person_pk}` | Single person detail with full resolved context, incl. masked `aadhaar_last4`; 404 if missing/inactive |
| GET | `/api/v1/person/persons/{person_pk}/addresses` | Active addresses for a person, with resolved address type + city/village/postal-code/district/state/country chain; 404 if the person doesn't exist |
| GET | `/api/v1/person/search` | Trigram similarity search (`pg_trgm`) on first/last name, plus prefix match on `person_id`/`mobile_number`; capped at 50 results |

`aadhaar_encrypted` and `aadhaar_hash` are never returned by any endpoint — only
`aadhaar_last4` for masked display (PER-BR-081). Full contract:
`docs/03_Solution/api/PERSON_API_CONTRACT.md`. Verified by 55 pytest integration tests
(`tests/api/test_person.py`; some of the original 61 were extracted into
`tests/security/test_*_security.py` — see `CLAUDE.md` → Tests & lint).

## Endpoints (Tier 4)

Originally 14 read-only endpoints across Family and Membership — no ORM, raw
parameterized SQL. **On the Tier 5 `membership.py`'s list/search gained
`require_permission("MEMBERSHIP_VIEW")` gating and its per-member endpoints an ownership check
(see the Membership table below); `family.py`'s 7 gained an ownership-based auth model instead**
(every endpoint now requires `get_current_user`, with `FAMILY_VIEW`/`FAMILY_MANAGE` as the admin
override — a deliberate design choice, not a gap), and `family.py` separately
**gained 9 more endpoints in Tier 5 (v0.11.0) — see below.**

**Family** — originally 7 read-only endpoints under `/api/v1/family`, across 5 tables (now
authenticated — see above):

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/family/families` | Family group list with filters + pagination (requires `FAMILY_VIEW`) |
| GET | `/api/v1/family/families/{family_group_pk}` | Family group detail (current member, or `FAMILY_VIEW`) |
| GET | `/api/v1/family/families/{family_group_pk}/members` | Family group members (current member or `FAMILY_VIEW`) |
| GET | `/api/v1/family/families/{family_group_pk}/head-history` | Family head history (current member or `FAMILY_VIEW`) |
| GET | `/api/v1/family/families/{family_group_pk}/graph?viewer_person_pk=` | Dynamic relationship-label computation via BFS traversal over `nss.family_link` edges (`api/services/family_graph.py`); covered by `tests/api/test_family_ownership.py`; current member or `FAMILY_VIEW` |
| GET | `/api/v1/family/families/{family_group_pk}/sakha-alignment` | FAM-036 majority-rule "effective Sakha" computation — `is_aligned` is hardcoded `True` by design; per-member `is_home_sakha` flags surface real mismatches; current member or `FAMILY_VIEW` |
| GET | `/api/v1/family/person/{person_pk}/membership-summary` | Bridges family context to membership context for a UI panel; self, a current relative, or `FAMILY_VIEW`; no test coverage yet |

Full contract: `docs/03_Solution/api/API_CONTRACT.md` (documents these 7 only, not yet updated
for the 9 below). Verified by 52 pytest integration tests
(`tests/api/test_family.py`, admin-token path; some of the original 67 were extracted into
`tests/security/`) plus 20 in `tests/api/test_family_ownership.py` (role-less JWT path, incl.
`/graph`) — `/person/{pk}/membership-summary` is the one endpoint with no coverage.

**Family (Tier 5 additions, released in v0.11.0) — 9 more endpoints, all requiring
`get_current_user` (JWT); the 2 `GET`s use the read pool, the 7 `POST`/`DELETE`s use
`get_write_connection` (`nss_db_writer`). The 7 writes (plus the admin list) are covered by
`tests/api/test_family_ownership.py`:**

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/family/person/{person_pk}/families` | Families a person belongs to (read pool; used by the member dashboard) |
| POST | `/api/v1/family/families` | Create a family — authenticated user becomes founding member + head; auto-generates the next `family_id`; uses the new `SELF` `RELATIONSHIP_TYPE` value |
| POST | `/api/v1/family/families/{pk}/members` | Add a member — requester must be the family's head or a family admin, or hold `FAMILY_MANAGE` (`_require_family_manage`) |
| DELETE | `/api/v1/family/families/{pk}/members` | Remove a member — same rule (FAM-048) |
| POST | `/api/v1/family/families/{pk}/links` | Create `family_link` graph edges — same rule |
| GET | `/api/v1/family/families/{pk}/admins` | List `family_admin` rows (current by default, or full history via `current_only=false`); current member or `FAMILY_VIEW` (read pool) |
| POST | `/api/v1/family/families/{pk}/admins` | Assign a Family Admin — requester must be the current head (FAM-046) or hold `FAMILY_MANAGE` (`_require_family_head`) |
| DELETE | `/api/v1/family/families/{pk}/admins` | Revoke a Family Admin — same rule (FAM-050) |
| POST | `/api/v1/family/families/{pk}/transfer-head` | Transfer family headship — head only, or `FAMILY_MANAGE` |

**Membership** — 8 endpoints under `/api/v1/membership`:

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v1/membership/members` | Member list with filters + pagination (`MEMBERSHIP_VIEW`) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}` | Member detail (`MEMBERSHIP_VIEW` or the member themself) |
| GET | `/api/v1/membership/search` | 7-field member search: `sangha_sevi_id`, `person_id`, `local_sakha_erp_id`, name (trigram 0.45), mobile, email, Kendra number (`MEMBERSHIP_VIEW`) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/affiliations` | Member Sakha affiliations, current + historical (`MEMBERSHIP_VIEW` or the member themself) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/parichaya-patra` | Member Parichaya Patra records (same) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/anumati-patra` | Member Anumati Patra records (same) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/journey` | Member journey events (same) |
| GET | `/api/v1/membership/organizations/{organization_pk}/darshak-summary` | `home_probationary_count` + `attending_from_other_sakha_count` for an org's Org Dashboard card (`MEMBERSHIP_VIEW`) |

Full contract and endpoint counts: `docs/03_Solution/api/API_CONTRACT.md`. Tests:
`tests/api/test_membership.py` (counts in `tests/README.md`).

## Known gaps (code-verified, this pass)

- **Stale module docstrings**: `foundation.py` ("17 GET ... No authentication"), `membership.py`
  ("7 GET ... No authentication"), `person.py` ("No authentication"), `admin.py` (lists 17 of its
  28 endpoints and still says short-code/create are "NSS_ERP_ADMIN only"), `auth.py` (omits
  `PATCH /profile` and the session endpoints), `registration.py` (lists only `POST /register`), `family.py` (its write list
  omits create-family and create-link), and `main.py` ("Verification UIs", "Read-only endpoints")
  no longer match their code. `middleware.py`'s docstring still says JS uses `?v=N` cache busting
  (now an automatic content hash, see `main.py`).
- **`/children-stats` and `/stats` recursion has no depth cap** — the SQL comments say "capped at
  depth 10" but neither CTE carries a depth column or `depth < 10` predicate; only `/hierarchy`
  does.
- **`API_PORT` is read by `config.py` but never used.**
- **`next_id()` ignores `id_sequence_master.padding_length`** (returns `prefix + current_value`).
- **`auth.py::forgot_password` does not deliver the OTP** (`# TODO: Send OTP via email/SMS`).

See `docs/PROJECT_DOCUMENTATION.md` → Key workflows for more detail on all six tiers.
