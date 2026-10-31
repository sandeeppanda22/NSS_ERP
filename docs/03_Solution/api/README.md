# docs/03_Solution/api/

API design documentation: request/response contracts for the FastAPI service implemented at
the root-level `api/` folder (raw psycopg2, no ORM; 17 routers, 251 endpoints — see
`api/README.md` for the running code). Each contract is written per-tier, as its vertical slice
lands, and stays DRAFT until the tier's implementation is frozen. The four per-tier contracts
were written when Tiers 0-3 were read-only and unauthenticated; in Tier 5
(v0.11.0) each now opens with a **Tier 5
update** note describing the JWT/permission gating, and `API_CONTRACT.md` carries the cross-tier
Tier 5 catalogue.
## Files

- **`BOOTSTRAP_API_CONTRACT.md`** (v1.1, DRAFT) — Tier 0 Bootstrap RBAC read-only contract: 4
  endpoints (`health`, `roles`, `permissions`, `roles/{pk}/permissions`) over 3 tables
  (`role_master`, `permission_master`, `role_permission`). No authentication (the only fully
  unauthenticated router); `nss_db_backend` connects SELECT-only. Permissions/mappings are
  now seeded in Tier 5, so those endpoints no longer return empty lists.
- **`FOUNDATION_API_CONTRACT.md`** (v1.2, DRAFT) — Tier 1 Foundation contract: documents 23 of the
  router's 33 endpoints (the festival-calendar, `sakha-postal-codes`, `/post-offices` and four
  member `*/propose` endpoints are catalogued only in `API_CONTRACT.md` §4) —
  17 reads across 11 tables (master data, system config, geography, runtime document metadata;
  now gated by `FOUNDATION_VIEW`) plus 6 Tier 5 writes (`POST`/`PATCH` master-data, settings,
  sequences; gated by `FOUNDATION_MANAGE`, §3.5). Carries forward Tier 0's conventions plus new
  Tier 1 ones (query-param filtering, hierarchical drill-down, no pagination).
  `nss.field_change_log` is not exposed by this router — `GET /api/v1/audit/change-log`
  (`AUDIT_VIEW`) serves it.
- **`ORGANIZATION_API_CONTRACT.md`** (v1.0, DRAFT) — Tier 2 Organization read-only contract: 8
  endpoints (`types`, `statuses`, `organizations` list/detail/children, `children-stats`,
  `stats`, `hierarchy`), exposing the NSS institutional hierarchy (Kendra → Anchalika/Zilla →
  Sakha → Patha Chakra). All gated by `ORGANIZATION_VIEW` in Tier 5; the body
  still describes the original 6-7 endpoints, with the update note at the top covering `/stats`.
- **`PERSON_API_CONTRACT.md`** (v1.0, DRAFT) — Tier 3 Person read-only contract (list/search
  need `PERSON_VIEW`; detail/addresses are self-or-`PERSON_VIEW` in Tier 5): 4 endpoints
  (`persons` list/detail, `persons/{pk}/addresses`, trigram `search`) over the `person` and
  `person_address` tables. Master-data FKs (gender, marital status, blood group, emergency
  relationship, address type) are resolved via JOINs; `aadhaar_encrypted`/`aadhaar_hash` are
  never returned — only `aadhaar_last4` for masked display.
- **`API_CONTRACT.md`** (`SOL-API-001`, v1.1.0, Draft) — a consolidated cross-tier quick
  reference covering Tiers 0–6 (Bootstrap/Foundation/Organization/Person/Family/Membership plus
  Authentication/Registration/Claim Approval/Administration/Audit, and Tier 6 Governance +
  Membership Change Requests) in one document: common
  conventions (pagination, sorting, error responses, audit-column exclusion, sensitive-data
  rules, UUID path parameters, the three authorization models), a condensed endpoint table per
  router with permission gates, frontend routes, and the full endpoint-count summary. It does **not** replace the per-tier contract docs above for Tiers 0–3 —
  those remain the source of full request/response detail, example payloads, and file maps. For
  Tier 4 (Family, Membership), Tier 5 (Auth/Admin/Registration/Claims/Audit) and Tier 6
  (Governance, Membership Change Requests, Correspondence, Attendance, Sakha re-parent approvals; on `feature/tier6-governance`, unmerged),
  `API_CONTRACT.md` is currently the **only** contract document — there is no dedicated
  `FAMILY_API_CONTRACT.md`, `MEMBERSHIP_API_CONTRACT.md`, Tier 5 or Tier 6 contract; request/response
  detail for those lives in the routers' module docstrings and Pydantic schemas.

Each per-tier contract documents conventions, the full endpoint catalogue with example
requests/responses and SQL patterns, a response-schema summary, error responses, and an
implementation file map tying the contract back to its router/schema/test/frontend files.
Write operations (POST/PATCH/DELETE) were deferred to Tier 5; they now exist (v0.11.0) — Foundation's six are specified in `FOUNDATION_API_CONTRACT.md` §3.5, everything
else in `API_CONTRACT.md` §7 and §9-§13.

See `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas for how this folder relates to the
actual implemented code under `api/`, and `docs/03_Solution/code_explanations/` for line-by-line
code walkthroughs of the same endpoints.
