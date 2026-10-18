# NSS ERP

Nilachala Saraswata Sangha Enterprise Resource Planning (NSS ERP)

---

# Overview

NSS ERP is a comprehensive web-based management platform being developed for Nilachala Saraswata Sangha.

The system is designed to support membership management, family management, governance, attendance tracking, Kumari Sangha, Kishor Puja, Founder & Heritage records, UPBS operations, reporting, and future NSS operational activities.

The project follows a:

```text
Database First
    ↓
API First
    ↓
UI First
```

design philosophy, ensuring that business rules are frozen before implementation.

---

# Project Objectives

* Centralized NSS member management
* Family-first relationship tracking
* Governance and committee management
* Attendance and review workflows
* Kumari Sangha and Kishor Puja management
* Founder & Heritage preservation
* UPBS operational support
* Historical record preservation
* Audit-compliant data management
* Role-based access control
* International branch support

---

# Technology Stack

> **Note:** `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` is the Approved
> forward-looking decision record — it replaces Bootstrap 5 with Tailwind CSS +
> DaisyUI + Alpine.js, and adds a hosting/offline plan. FastAPI is now the sole, implemented
> API layer (Tiers 0-6); the stack below reflects the current codebase.

## Frontend

* Tailwind CSS + DaisyUI (pre-built via Tailwind CLI, no longer CDN — see `package.json`,
  `tailwind.config.js`, `frontend/assets/css/tailwind-input.css`/`tailwind.min.css`) + Alpine.js
  (CDN) — no frontend framework. Node.js is only needed to rebuild CSS after a class change
  (`npm install && npm run css:build`); the built CSS is committed, so a fresh clone runs
  without Node.js.
* `frontend/` consists of exactly four pages: `login.html` (at `/login`, which `/` also
  302-redirects to), `register.html` (at `/register`), `dashboard.html` (at `/dashboard` — the
  role-aware member dashboard, see `docs/03_Solution/architecture/MEMBER_DASHBOARD.md`; tabs:
  Personal, Membership, Family, Attendance, Governance, Documents, plus role-based admin tabs
  incl. an Org Dashboard), and `admin.html` (at `/admin` — the administration console; tabs:
  Users, User Detail, Create User, Create Sangha-Sevi, Password, Create Organization,
  Organizations, Assign Sakhas, Registration Approvals (claims), Geo Approvals, Person Directory, Member
  Directory, Organization Hierarchy, Org Dashboard, Reference Data, Geography, System
  Settings), plus their `assets/js/*.js` files (`login.js`, `register.js`, `dashboard.js`,
  `admin.js`, `auth.js`, `org-dashboard.js`, and the shared helpers `nss-config.js`/
  `nss-datepicker.js`/`nss-combobox.js`/`nss-dialog.js`/`nss-location.js`/`nss-layout.js`). The Tier 0-4
  standalone verification pages (`index.html`, `foundation.html`, `organization.html`,
  `person.html`, `family.html`, `membership.html`) and their per-page JS have been **deleted**;
  their functionality was folded into `admin.html` (Foundation → Reference Data / Geography,
  Organization → Organizations / Organization Hierarchy, Person → Person Directory, Membership →
  Member Directory) and `dashboard.html` (Family → Family tab, incl. the family-tree
  visualization and Sakha-alignment mismatch badges; Membership → Membership tab).
  **`claim-approval.html` does not exist** — the registration-claim review queue backed by
  `api/routers/claim_approval.py` is served by `admin.html`'s Registration Approvals tab, and
  there is deliberately no `forgot-password.html` (forgot/reset-password is inline on the login page). All pages
  are served by FastAPI, which rewrites each page's `/assets/*` references to a
  content-hashed `?v=` URL per request; see `frontend/README.md` for the full file/function
  reference. 13 static mockups for later tiers exist under `docs/03_Solution/ui/mockups/`.

---

## Backend

* FastAPI — the only web/API layer in the codebase (`api/`, raw `psycopg2`, no ORM):
  15 routers (201 endpoints; `governance.py`, `membership_change_request.py` and `correspondence.py` are Tier 6 and still uncommitted on `feature/tier6-governance`), one per tier/module (per-router endpoint counts: `api/README.md` and
  `docs/03_Solution/api/API_CONTRACT.md`); `bootstrap.py` is the only unauthenticated router
  besides public registration.
  Tiers 1-4 GET endpoints are gated by `require_permission(...)` (Foundation/Organization/
  Person/Membership lists) or an ownership model (Family; Person/Membership detail and
  sub-resources) — see `docs/03_Solution/api/API_CONTRACT.md`. **Tier 5 is released as v0.11.0 (merged to `develop`/`main`).** See `CLAUDE.md`, `docs/PROJECT_DOCUMENTATION.md` → Architecture,
  `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`, and `docs/03_Solution/api/API_CONTRACT.md`.
* Django — an earlier prototype existed under `backend/` but was fully archived and removed
  once the FastAPI direction was adopted; `backend/` no longer exists on disk (Git history only).

---

## Database

* PostgreSQL

---

## Authentication

* **Tiers 0-4 were originally deliberately unauthenticated by design (read-only).** JWT-based
  authentication + RBAC is now implemented — Argon2 password hashing, access/refresh JWTs,
  `nss.user_account`/`password_history`/`registration_claim`/`password_reset_token` tables,
  seeded `permission_master`/`role_permission`, and role/scope-based authorization — but
  **released in v0.11.0**. Only Tier 0's 4 `bootstrap.py` endpoints and the public `/api/v1/register/*`,
  `/auth/login|refresh|forgot-password|reset-password` endpoints need no JWT. Reads connect as
  `nss_db_backend` (SELECT-only); writes connect as a second role, `nss_db_writer`. A DB-level
  trigger (`fn_audit_trigger()`) records every `nss.*` INSERT/UPDATE/DELETE to
  `nss.system_event_log` and, per changed field, to `nss.field_change_log`.

---

## Deployment

* Render.com — `render.yaml` (repo root) defines a free-tier web service (`uvicorn
  api.main:app --workers 2`). It does not provision a database itself; `DB_NAME`/`DB_USER`/
  `DB_PASSWORD`/`DB_HOST`/`DB_PORT` (plus the Tier 5 `DB_WRITE_USER`/`DB_WRITE_PASSWORD`/
  `JWT_SECRET_KEY`) are set manually in the Render dashboard, pointing at an external Neon.dev
  PostgreSQL instance. `render_build.sh` builds the Tailwind CSS, installs Python deps and then
  runs the DB bootstrap (phases 0-14, incl. 11b/11c governance DDL + seed; the optional Phase 15 demo seed via `RUN_DEMO_SEED` exists only in `02_build.sh`/`.ps1`, not here) on every deploy, existence-gated per table
  (`to_regclass`: an existing table's DDL and seed are skipped, only new tables are created and
  seeded), so a re-run is idempotent — note this means an already-existing table's seed content
  (or a changed constraint) is never re-applied by a routine redeploy, only by a full hard
  rebuild, see `docs/03_Solution/architecture/GETTING_STARTED.md` §7a-2; `RUN_DB_BOOTSTRAP`
  (`true`/`1`/`yes`/`on`,
  case/whitespace-insensitive; default: off) gates **only** the Phase 13 admin seed. Not yet run in production; see
  `docs/03_Solution/architecture/DEPLOYMENT_PROCEDURE.md`.

---

## Future Enhancements

* Redis Cache
* Background Workers
* Mobile Application
* API Integrations

---

# Project Architecture

```text
Browser / HTTP client
   │
   ▼
Security Middleware (CORS, rate limiting, security headers, CSP, Cache-Control)
   │
   ▼
FastAPI (api/main.py — 15 routers: bootstrap, foundation, organization, person, family,
   │       membership, auth, registration, claim_approval, admin, audit, geo_approval,
   │       governance, membership_change_request, correspondence — the last three are Tier 6)
   │       JWT + RBAC guards (api/dependencies/), services (api/services/)
   ▼
psycopg2 connection pools (api/database.py) — read pool (nss_db_backend) + write pool
   │       (nss_db_writer), raw SQL, no ORM
   │
   ▼
PostgreSQL (nss.* schema)
```

*(See `docs/03_Solution/code_explanations/` for full line-by-line walkthroughs of
every source file, organized by layer — `API_CODE_EXPLANATIONS.md`,
`DATABASE_CODE_EXPLANATIONS.md`, `UI_CODE_EXPLANATIONS.md`, `SECURITY_CODE_EXPLANATIONS.md`,
`TESTING_CODE_EXPLANATIONS.md`.)*

---

# Getting Started

See [`docs/03_Solution/architecture/GETTING_STARTED.md`](docs/03_Solution/architecture/GETTING_STARTED.md) for full setup instructions (database, API, tests) and database rebuild procedures.

---

# Core Principles

## Person ≠ Member

A Person may exist without being a Member.

Examples:

* Family Member
* Kumari Participant
* Kishor Participant
* Future Applicant
* Historical Person

A Member must always be a Person.

---

## Family First

Family relationships are maintained independently of membership status.

---

## History Never Deleted

Business records are preserved permanently.

Physical deletion is avoided.

Soft delete is preferred.

---

## Audit First

All critical business operations must be auditable.

---

## Master Data Driven

Business configuration is controlled through master tables rather than hardcoded values.

---

## Global Ready

The system is designed to support NSS activities within India and internationally.

---

# Organization Hierarchy

```text
KENDRA
├── ANCHALIKA_SANGHA
│   └── SAKHA_SANGHA / SAKHA_ASANA
│       ├── KUMARI_SANGHA
│       ├── SEVAK_SANGHA
│       └── MAHILA_SANGHA          (local, per-Sakha)
├── ZILLA_SANGHA
│   └── SAKHA_SANGHA / SAKHA_ASANA
│       ├── KUMARI_SANGHA
│       ├── SEVAK_SANGHA
│       └── MAHILA_SANGHA          (local, per-Sakha)
├── PATHA_CHAKRA
├── PARIBARIK_SANGHA                ("Gruhasana" — see notes)
└── MAHILA_SANGHA                   (Kendra / Central — exactly one)

NILACHALA_KUTIRA   — unique, no parent, no children; peer of KENDRA, not under it
SMRUTI_MANDIRA     — unique, no parent, no children; peer of KENDRA, not under it
```

Notes:

* `ANCHALIKA_SANGHA` and `ZILLA_SANGHA` are siblings directly under `KENDRA` — never nested
  under each other.
* `SAKHA_SANGHA`/`SAKHA_ASANA` sit only under `ANCHALIKA_SANGHA` or `ZILLA_SANGHA`.
* `KUMARI_SANGHA`/`SEVAK_SANGHA` sit only under `SAKHA_SANGHA`.
* `MAHILA_SANGHA` is **one type, two tiers, distinguished by parent** — `parent = KENDRA`
  identifies the single Kendra/Central Mahila Sangha; `parent = SAKHA_SANGHA` identifies a
  local, per-Sakha Mahila Sangha. The Bye-Law's central-supervises-branches relationship is a
  governance relationship, deliberately *not* encoded as a parent-child org edge.
* `PARIBARIK_SANGHA` ("Paribarik Sangha", family organisation attached to Kendra — Bye-Law
  Preamble) sits directly under `KENDRA`. It is org-level, not tied to an individual person.
* `PARIBARIK_ASANA` ("Gruhasana") is conceptually attached to a `sangha_sevi` (a person's
  membership record), not to another organization — that `sangha_sevi` belongs to exactly one
  `SAKHA_SANGHA`. Since `nss.organization` has no direct link to `sangha_sevi` today, its
  `parent_organization_pk` is set to that person's current Sakha Sangha as an implementation
  proxy, not a literal org-tree claim.
* `PATHA_CHAKRA` may operate within India or internationally.
* Admin scope levels (`nss.admin_scope`/`nss.role_master.scope_level`) cover `NSS-WIDE`,
  `KENDRA`, `ANCHALIKA`, `ZILLA`, `SAKHA`, `PATHA_CHAKRA`, and `KENDRA_MAHILA_SANGHA` only — no
  role is scoped to `SAKHA_ASANA`, `KUMARI_SANGHA`, `SEVAK_SANGHA`, `PARIBARIK_SANGHA`, or
  `PARIBARIK_ASANA`.

> **Frozen (2026-09-25):** the type-to-type parent compatibility matrix above is now frozen —
> see `docs/03_Solution/modules/organization/04_organization_business_rules.md` §28
> (ORG-BR-087–095), an explicit governance decision. This supersedes the prior "open item"
> framing (the matrix used to be left undecided; only the generic apex + self-referencing
> structure was frozen).

> **Frozen separately:** a **13-type inventory** (`docs/03_Solution/modules/organization/
> 04_organization_business_rules.md` ORG-BR-064 lists the earlier 8; the remaining 5 —
> `PARIBARIK_SANGHA`, `PATHA_CHAKRA`, `KUMARI_SANGHA`, `SEVAK_SANGHA`, `MAHILA_SANGHA` — are
> seeded in `database/seed/01_foundation/02_master_data.sql` under `ORGANIZATION_TYPE`).

> **Open:** the frozen 3-table structure is no longer what's implemented in SQL — the former
> `organization_type_master`/`organization_status_master` tables were retired in favor of rows
> in Foundation's generic `master_data` (see `docs/PROJECT_DOCUMENTATION.md` → Gotchas for the
> full reconciliation status).

---

# Module Structure

*The sections below describe the full planned module roadmap. Foundation, Organization,
Person, Family, Membership, plus (v0.11.0) Authentication and Administration
are the only modules on this list with API/backend implementation so far — see Current
Development Status below for full endpoint/table counts — plus SQL DDL for Bootstrap RBAC,
Foundation, Organization, Person, Family, Membership, Authentication, and Administration. An earlier Django prototype briefly
implemented parts of Foundation, Membership, Family, Governance (stub), Attendance (stub), and
Founder & Heritage under `backend/`, but it was fully archived and removed once the FastAPI
direction was adopted. Solution-layer design documentation (overview/ERD/lifecycle/business-
rules/table-design) is complete for essentially every module on this roadmap — ahead of, and not
yet reconciled with, any code implementation for the modules beyond those listed above.
**Programmes & Events is the one exception**: still DRAFT, explicitly not frozen, though its
cross-module reconciliation gates are closed and its candidate table set has settled.
See `docs/PROJECT_DOCUMENTATION.md` for the current, code-verified status of each.*

## Foundation

* Organization Management
* Person Management
* Master Data
* Authentication & RBAC
* Audit & History
* Global Location Management

---

## Membership

* Member Registration
* Membership Types
* Membership Approval
* Renewal
* Transfer
* Membership Journey
* Sangha Sevi ID Management

---

## Family

* Family Dashboard
* Family Tree
* Relationship Management

---

## Governance

* General Body
* Governing Body
* Advisory Board
* Committees
* Position Assignment

---

## Attendance

* Weekly Attendance
* Attendance Review
* Attendance Reports

---

## Mahila Sangha

* Membership
* Activities
* Governance

---

## Kumari Sangha

* KM Identity
* Activities
* Training
* Membership Transition

---

## Kishor Puja

* KH Identity
* Registration
* Guardian Assignment

---

## Sevak Sangha

* Volunteer Development
* Training
* Activities

---

## Founder & Heritage

* Biography
* Philosophy
* Teachings
* Publications

---

## UPBS

* Registration
* Accommodation
* Committee Management
* Reports

---

## Reports & Analytics

* Membership Reports
* Attendance Reports
* Governance Reports
* UPBS Reports

---

## Administration

* Users
* Roles
* Permissions
* System Settings

---

# Database Design Principles

## Person Module

```text
Person ≠ Member
```

A Person may exist without Membership.

A Member must always be linked to a Person.

---

## Contact Information

Supports:

* International Phone Numbers
* Country Phone Codes
* Email Addresses

Rules:

* Mobile Number + Country Phone Code must be unique.
* Email is not required to be unique.
* At least one contact method is mandatory.

---

## Address Management

Supports:

* Multiple Addresses
* Primary Address Selection
* Global Locations
* Postal Code Mapping

Rules:

* One Person may have multiple addresses.
* Only one address may be Primary.
* Primary Address may be changed at any time.

---

## Location Hierarchy

```text
Country
    ↓
State / Province
    ↓
District / Region
    ↓
City / Village
```

Postal Codes are maintained separately and linked through mapping tables.

---

# Development Workflow

## Branch Strategy

```text
main
 └── develop
      └── feature/*
```

---

## Feature Development Workflow

```text
Create Feature Branch
        ↓
Implement Changes
        ↓
Commit Changes
        ↓
Merge into develop
        ↓
Create Release Notes
        ↓
Create Git Tag
        ↓
Merge develop into main
        ↓
Create GitHub Release
```

---

# Release Management

Every version must include:

* Git Tag
* Release Notes Document
* GitHub Release

Release Notes Location:

```text
docs/05_Releases/
```

Examples:

```text
v0.1.0.md
v0.2.0.md
v0.2.1.md
v0.3.0.md
v0.4.0.md
v0.5.0.md
v0.5.1.md
v0.6.0.md
v0.7.0.md
v0.8.0.md
v0.9.0.md
v0.10.0.md
v0.10.1.md
v0.10.2.md
v0.10.3.md
v0.10.4.md
v0.11.0.md
```

`docs/05_Releases/README.md` is the index.

---

# Completed Milestones

## v0.1.0

Initial Project Setup

---

## v0.2.0

Foundation Models

---

## v0.2.1

Admin Setup

---

## v0.3.0

UI Foundation and Authentication Complete

---

## v0.4.0

Organization Module Design Complete *(design/ERD/business-rules/table-design docs only — see
v0.5.1+ and Current Development Status below for the later SQL implementation)*

---

## v0.5.0

Person Module Design Complete

---

## v0.5.1

Person Database Schema Complete

* Global Location Model
* Person Schema
* Person Address Schema
* International Mobile Support
* Address Mapping Model

---

## v0.6.0

Full-Stack Tier 0 — Documentation, Database, API, UI, and Deployment

* 22-module solution documentation complete (overview, ERD, lifecycle, business rules, table design)
* 5 architecture documents frozen (SOL-ARCH-007 through SOL-ARCH-011)
* 18-table database implementation (Bootstrap RBAC + Foundation + Organization vertical slices)
* FastAPI Tier 0 bootstrap API (4 read-only endpoints)
* Bootstrap Verification UI (responsive 3-column layout, Tailwind + DaisyUI + Alpine.js)
* Render.com + Neon.dev deployment configuration
* Project governance standards and authoritative reference corpus
* NSS-WIDE scope for SYSTEM roles
* Terminology corrections (Kishor, Bye-Law, statutory)

---

## v0.7.0

Tier 1 Foundation — API, Web UI, Security Hardening

* FastAPI Tier 1 Foundation API (17 read-only endpoints across 11 tables)
* Tier 1 Foundation Verification UI (4-tab layout: Master Data, System Config, Geographic
  drill-down, Runtime Tables)
* Cross-tier security-hardening middleware (security headers, opt-in CORS, rate limiting via
  `slowapi`) + CDN Subresource Integrity pinning (DaisyUI, Alpine.js)
* Test suite grown from 9 to 64 tests (Tier 0 + Tier 1 Foundation + security middleware)
* `pytest`/`httpx` pinned in `requirements.txt`; both security audit reports updated to v1.1
* Code-explanation docs reorganized from 3 per-tier files to 5 per-layer files
  (API/Database/UI/Security/Testing)

---

## v0.8.0

Tier 2 Organization — API, Web UI

* FastAPI Tier 2 Organization API (6 read-only endpoints, incl. a self-referencing hierarchy
  tree via a `WITH RECURSIVE` CTE)
* Organization contact and online-presence fields (8 new columns on `nss.organization`)
* Tier 2 Organization Verification UI (3-tab layout: Reference Data, Organizations, Hierarchy)
* Test suite grown from 64 to 139 tests (Tier 0 + Tier 1 + Tier 2 + security middleware)
* `TIER2_SECURITY_AUDIT.md` added — no blocking findings
* `code_explanations/` and API contracts (`docs/03_Solution/api/`) moved out of `architecture/`

---

## v0.9.0

Organization Master-Data Migration + Tier 3 Person — API, Web UI

* Organization master-data migration: `organization_type_master`/`organization_status_master`
  retired in favor of Foundation's `master_category`/`master_data` (10 org types, unified
  13-value `STATUS` category)
* FastAPI Tier 3 Person API (4 read-only endpoints, incl. `pg_trgm` fuzzy search)
* Person DDL rewrite onto the Foundation `master_data` pattern (`person`, `person_address`)
* Shared `api/helpers.py` (cursor→Pydantic + pagination), adopted by Organization too, plus
  `limit`/`offset` pagination on Organization's list/hierarchy endpoints
* Tier 3 Person Verification UI (2-tab layout: Persons, Search)
* Test suite grown from 139 to 208 tests (Tier 0 + Tier 1 + Tier 2 + Tier 3 + security)
* `TIER3_SECURITY_AUDIT.md` added — no blocking findings, Aadhaar defence-in-depth confirmed

---

## v0.10.0 — v0.10.4

Tier 4 Family + Membership — full vertical slice, family graph, Organization `children-stats`
(v0.10.0, 14 read-only endpoints), followed by four hotfix tags: `family_link` build wiring and
Render parity (v0.10.1), Neon role bootstrap (v0.10.2), idempotent DDL + seed (v0.10.3), and a
performance-hardening pass (v0.10.4 — connection pool, composite partial indexes, `--workers 2`).
See `docs/05_Releases/` for each.

---

# Current Development Status

> Bullets under "Completed" record each slice **as it was when delivered/released** (e.g. "no
> auth", "7 read-only endpoints"). Tier 5 (released) has since gated most of those
> endpoints and added more, and Tier 6 (in progress) added more again; the Tier 5/6 bullets at the end of the list and
> `docs/03_Solution/api/API_CONTRACT.md` carry the current counts.

Completed:

* Foundation Architecture
* Authentication Foundation
* Organization Module Design (v1.1.0+, GOVERNANCE ALIGNED; the type-to-type parent hierarchy was
  frozen 2026-09-25, ORG-BR-087–095 — see Organization Hierarchy above)
* Person Module Design (v2.0.0, FROZEN — 2 tables: `person`, `person_address`; `document_master`
  is owned by Foundation, see below)
* Person Database Schema (complete — `person` (28 columns) + `person_address` implemented under
  `database/ddl/03_person/`, superseding the v0.5.1 prototype by following the Foundation
  `master_data` pattern: gender/marital status/blood group/emergency relationship/address type
  resolve via `nss.master_data`, not dedicated per-domain master tables)
* Foundation Database Schema ("Foundation Vertical Slice" — 12 tables + full seed data under
  `database/ddl/01_foundation/`/`database/seed/01_foundation/`, plus (Tier 5) a 13th,
  `system_event_log`, and the audit trigger — 11 of the original 12 tables are consumed by the
  Tier 1 Foundation API, see below; `field_change_log` is read via the Tier 5
  `GET /api/v1/audit/change-log`, not Foundation)
* Organization Database Schema ("Organization Vertical Slice" — 1 table (`organization`) + full
  seed data under `database/ddl/02_organization/`/`database/seed/02_organization/`; the former
  `organization_type_master`/`organization_status_master` tables were retired in favor of
  Foundation's generic `master_data` (categories `ORGANIZATION_TYPE`, 13 values; `STATUS`, 13+
  values, shared across modules) — now consumed by the Tier 2 Organization API (see below). This
  diverges from the frozen 3-table module design — see `docs/PROJECT_DOCUMENTATION.md` →
  Gotchas. Combined with Foundation, Bootstrap RBAC, Person, Family, Membership, Authentication +
  Administration (Tier 5) and Governance (Tier 6, uncommitted): **64 tables implemented** — see `database/README.md`)
* Bootstrap RBAC DDL (`role_master`/`permission_master`/`role_permission`, `SOL-BOOT-001`/
  `SOL-ARCH-011` — DDL implemented and committed; `role_master` seeded with 10 roles
  (incl. `NSS_ERP_ADVISORY_BOARD_ADMIN`, Tier 6); `permission_master` (25 permissions, incl.
  `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`, `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE`)/`role_permission` are now seeded too (Tier 5/6); ownership stays with Administration,
  see `docs/PROJECT_DOCUMENTATION.md` → Gotchas for a role-catalogue discrepancy this surfaced)
* FastAPI Tier 0 Bootstrap API (`api/` — 4 read-only endpoints: health check, roles,
  permissions, role→permissions; no auth, no ORM, raw `psycopg2` against `nss.*`, connects as
  `nss_db_backend`; the Django prototype that previously lived under `backend/` was archived
  and removed)
* Tier 0 Bootstrap Verification UI (`frontend/` — Tailwind CSS + DaisyUI (pre-built via Tailwind
  CLI, no longer CDN) + Alpine.js, served as static files by FastAPI; 4 sections: system status,
  RBAC roles, permissions, interactive role→permissions drill-down)
* FastAPI Tier 1 Foundation API (`api/routers/foundation.py` — 17 read-only endpoints across
  11 tables: master data, system settings, ID sequences, geography (country → state → district
  → city/village + postal codes), and document_master; `field_change_log` deliberately not
  exposed, deferred to Tier 5; no auth, no ORM, backed by 59 pytest integration tests — see
  `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`)
* Tier 1 Foundation Verification UI (`frontend/foundation.html` + `assets/js/foundation.js` —
  4-tab layout: Master Data, System Config, Geographic drill-down, Runtime Tables) — **page since
  retired and deleted; this functionality now lives in `admin.html`'s Reference Data and
  Geography tabs**
* Released as v0.7.0 — merged to `main`
* FastAPI Tier 2 Organization API (`api/routers/organization.py` — 6 read-only endpoints under
  `/api/v1/organization`: reference data (types, statuses), organization records (list with
  `type_code`/`status_code` filters, single-record lookup, children), and a self-referencing
  hierarchy tree via `WITH RECURSIVE`; no auth, no ORM, backed by 64 pytest integration tests —
  see `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md`)
* Tier 2 Organization Verification UI (`frontend/organization.html` +
  `assets/js/organization.js` — 3-tab layout: Reference Data, Organizations, Hierarchy) — **page
  since retired and deleted; this functionality now lives in `admin.html`'s Organizations and
  Organization Hierarchy tabs**
* Implemented and released as v0.8.0 — merged to `main`
* FastAPI Tier 3 Person API (`api/routers/person.py` — 4 read-only endpoints under
  `/api/v1/person`: person list with `gender_code`/`marital_status_code`/`blood_group_code`
  filters and pagination, person detail, person addresses, and trigram-based (`pg_trgm`) name
  search; gender/marital status/blood group/emergency relationship/address type resolved via
  JOINs against Foundation's `master_data`; `aadhaar_encrypted`/`aadhaar_hash` are never
  returned — only `aadhaar_last4` for masked display (PER-BR-081); no auth, no ORM, backed by
  61 pytest integration tests — see `docs/03_Solution/api/PERSON_API_CONTRACT.md`)
* Tier 3 Person Verification UI (`frontend/person.html` + `assets/js/person.js` — Persons/Search
  tab layout structurally parallel to the Organization Verification UI) — **page since retired
  and deleted; this functionality now lives in `admin.html`'s Person Directory tab**
* Implemented and released as v0.9.0 — merged to `main`
* FastAPI Tier 4 Family API (`api/routers/family.py` — 7 read-only endpoints under
  `/api/v1/family`: family list with filters and pagination, family detail, family members
  (relationships per family), family head history, plus 3 newer endpoints — `/graph`
  (dynamic relationship-label computation via BFS traversal over `nss.family_link` edges, in a
  new `api/services/family_graph.py` — no test coverage yet), `/sakha-alignment` (FAM-036
  majority-rule "effective Sakha" computation with per-member mismatch flags), and
  `/person/{pk}/membership-summary` (bridges family context to membership context — also no
  test coverage yet); no auth, no ORM, backed by 67 pytest integration tests)
* FastAPI Tier 4 Membership API (`api/routers/membership.py` — 7 read-only endpoints under
  `/api/v1/membership`: member list with filters and pagination, member detail, a 7-field
  member search (Sangha Sevi ID, person ID, local Sakha ERP ID, name trigram, mobile, email,
  Kendra number) plus a 4-field person search, Sakha affiliation history, Parichaya Patra and
  Anumati Patra records, and journey-event timeline per member; three-tier identity model —
  Sangha Sevi ID (NSS-wide, permanent), Local Sakha Number (Sakha-scoped, auto-generated),
  Kendra Number (annual per FY, on `parichaya_patra.document_number`); no auth, no ORM, backed
  by 99 pytest integration tests — the largest test file in the repo)
* FastAPI Tier 2 Organization API grew a 7th endpoint, `/organizations/{pk}/children-stats`
  (aggregate family/member/person counts per direct child, recursing through descendant
  Sakhas and reusing the same FAM-036 majority-rule computation — implemented independently
  from Family's version, a real SQL duplication; its own docstring claims org-admin-sidebar UI
  wiring that does not exist in `admin.html`/`admin.js`'s Organization Hierarchy tab — which
  absorbed the deleted `organization.html`/`organization.js` — either)
* Tier 4 Family Verification UI (`frontend/family.html` + `assets/js/family.js` — now includes
  a family-tree visualization, viewer selector, and Sakha-alignment mismatch badges) and Tier 4
  Membership Verification UI (`frontend/membership.html` + `assets/js/membership.js`) — **both
  pages since retired and deleted; this functionality now lives in `dashboard.html`'s Family and
  Membership tabs, with the administrative member lookup in `admin.html`'s Member Directory tab**
* New shared frontend config: `frontend/assets/js/nss-config.js` (display-name overrides —
  `PROBATIONARY` → "Darshaka" — badge-class lookup maps, document-visibility rules) and
  `frontend/assets/css/badges.css` (every badge CSS class, single source of truth) — at the time,
  all 6 verification pages included both; both files survive the page retirement and are now
  included by `admin.html`/`dashboard.html`; no per-page duplicate inline badge styles
* Family DDL (5 tables: `family_group`, `family_relationship`, `family_head_history`,
  `family_transition_history`, `family_link` — the last stores only direct
  parent/spouse edges; every other kinship term is computed dynamically) and Membership DDL
  (12 tables: `sangha_sevi` plus
  status/renewal/transfer/affiliation/journey/review history tables, `parichaya_patra`/
  `anumati_patra` and their history tables) under `database/ddl/04_family/`/`05_membership/`
* *(Historical)* a `database/migrations/` folder and two `database/seed/99_*.sql`
  verification-data scripts were added here; all of them — and every Tier 4 demo seed file —
  have since been **deleted** in Tier 5 (a fresh build seeds zero demo
  Person/Family/Membership rows)
* New consolidated `docs/03_Solution/api/API_CONTRACT.md` (cross-tier reference) and security-audit docs moved from `code_explanations/` to a dedicated
  `docs/03_Solution/security/` folder (now including `TIER4_SECURITY_AUDIT.md`)
* New `test_data_integrity.py` (23 tests, now `tests/db/test_data_integrity.py`) — cross-module
  smoke tests
* Merged to `develop` and `main`, tagged `v0.10.0` (see `docs/05_Releases/v0.10.0.md`)
* Hotfix tags followed v0.10.0 (release notes for each are in `docs/05_Releases/`): `v0.10.1`
  (wired `family_link` into `02_build.sh`/`render_build.sh`, extended `render_build.sh` through
  the full Tier 4 phase sequence), `v0.10.2` (creates `nss_db_owner`/`nss_db_backend` roles on
  Neon before granting — `render_build.sh` was failing at the grant step on a fresh Neon
  deploy), `v0.10.3` (root-cause idempotency fix: every `CREATE TABLE`/`INDEX` in `database/ddl/`
  now uses `IF NOT EXISTS`, every seed `INSERT` is now an upsert — fixes a production Neon
  database that was silently missing newer `master_data` columns/rows because a multi-`INSERT`
  seed file aborted partway through on the first pre-existing row)
* `v0.10.4` — performance-hardening pass (composite partial indexes for the FAM-036 CTE hot
  path, Uvicorn `--workers 2`, connection pool `minconn` 1→2, non-blocking frontend fetches);
  merged `performance-optimization` → `develop` → `main` (see `docs/05_Releases/v0.10.4.md`)
* Global Location Model
* Membership Module Design (v1.0, DRAFT — table/column shapes now match the implemented DDL,
  but the design doc itself hasn't been reconciled to FROZEN yet)
* Family Module Design (v1.0, DRAFT — same: implemented DDL matches, doc still DRAFT)
* Attendance Module Design (Review Workflow Frozen)
* Founder & Heritage Module Design (v1.0.0, SOURCE ALIGNED — 8 tables designed; zero
  implementation exists for any of them)
* Kumari Sangha Module Design (v1.0.0, SOURCE ALIGNED)
* Kishor Puja Module Design (v1.0.0, SOURCE ALIGNED — Guardian Model frozen v2.1)
* Mahila Sangha Module Design (v2.1.0, Bye-Law-aligned governance model)
* Sevak Sangha Module Design (partially frozen — table design only; see
  `docs/PROJECT_DOCUMENTATION.md`)
* Foundation Module Design (v1.0.0, SOURCE ALIGNED — describes 10 tables: the original 8
  master-data/geography/sequence tables plus `document_master` + `field_change_log`).
  **SQL implements 12 tables** (2
  more than the design doc covers — see Foundation Database Schema above and
  `docs/PROJECT_DOCUMENTATION.md`)
* Administration Module Design (v1.0.0/v1.2.0, SOURCE ALIGNED — 8 Administration-owned tables:
  5 RBAC tables plus the Correspondence Register; table-design doc frozen at v1.2.0 for the
  parallel administrative role model (`SOL-ADMIN-004`); `user_account`/`password_history` are
  exclusively Authentication-owned)
* Authentication & Security Module Design (v1.0.0, SOURCE ALIGNED — exclusively owns
  `user_account`+`password_history`; references but doesn't own Administration's 5 RBAC tables;
  no corresponding API/backend implementation exists yet)
* Governance Module Design (v1.0.0, SOURCE ALIGNED — Unified Body Governance Model + Elections,
  9 tables designed; the Tier 6 SQL implements 10 — adds `election_vote_participation`; freezes the Mahila Parichalana Mandali term at 3 years, conflicting with the Mahila
  module's own frozen 2-year term — unreconciled, see `docs/PROJECT_DOCUMENTATION.md`)
* Publications Module Design (v1.0.0, SOURCE ALIGNED + USER REQUIREMENTS — zero new tables,
  reuses Founder & Heritage's publication tables)
* UPBS Module Design (v1.0.0, SOURCE ALIGNED — 7 tables)
* Reports & Analytics Module Design (v1.0.0, SOURCE ALIGNED — 5 metadata/config-only tables)
* Audit Module Design (v1.0.0, SOURCE ALIGNED — 2 tables)
* Backup & Technical Module Design (v1.0.0, SOURCE ALIGNED — 2 tables)
* Finance Module Design (v1.0.0, SOURCE ALIGNED — 7 tables: financial_year, financial_scope,
  fund_master, financial_transaction, financial_receipt, financial_payment, financial_transfer;
  derives from NSS Bye-Law Section F and Mahila Sangha Bye-Law Clause 7)
* Programmes & Events Module Design (Module #21, v0.1.0, DRAFT — NOT FROZEN — Programme Type →
  Event Instance two-level model; 7 candidate common tables, all cross-module reconciliation
  gates closed (`SOL-EVT-007`) but no table frozen DDL yet)
* Assets & Property Module Design (Module #22, v1.0.0, SOURCE ALIGNED — 7 tables: property,
  asset, custodianship, property_statutory_record, maintenance_record, property_document,
  asset_document; 74 business rules)
* Frontend CSS build migration (since released): Tailwind CSS +
  DaisyUI moved from CDN (`<script src="https://cdn.tailwindcss.com">` + DaisyUI CDN `<link>`)
  to a pre-built, tree-shaken, minified stylesheet (`frontend/assets/css/tailwind.min.css`,
  ~87 KB) generated via Tailwind CLI (`package.json`, `tailwind.config.js`); every page
  `<link>`s the built file (a committed artifact — Node.js is only needed to rebuild it);
  `render_build.sh` runs `npm install` + the Tailwind build before Python deps. `api/middleware.py` gained a `Cache-Control: public, max-age=86400,
  must-revalidate` header on `/assets/*` responses (previously only `/api/*` had a Cache-Control
  value at all) — now asserted in `tests/security/test_security_headers.py`. The logo asset
  (`frontend/assets/img/nss-logo.png`) was also compressed (1.4 MB → ~100 KB), with the original
  kept as `nss-logo-original.png`.
* **Tier 5 — Authentication + Administration (v0.11.0):**
  11 new tables — `user_account`, `password_history`, `registration_claim`,
  `password_reset_token`, `user_session` (`database/ddl/06_authentication/`); `user_role`, `admin_scope`
  (`07_administration/`); `family_admin` (Family), `darshak_attendance_registration` and
  `credential_sequence_counter` (Membership); and `system_event_log`
  (`01_foundation/14_system_event_log.sql`) backed by a database-level `fn_audit_trigger()`
  (`15_audit_trigger.sql`, `SOL-AUDIT-004`) that fires on every INSERT/UPDATE/DELETE across
  `nss.*` tables — actor identity comes from per-request session variables, so writes can't
  bypass the audit trail; `api/helpers.py::log_audit()` also records explicitly from write
  endpoints. **48 tables at release** (incl. `post_office`/festival tables added later on the branch). New routers at that point: `auth.py` (8 endpoints then; 10 now), `registration.py` (6 then; 12 now,
  public), `claim_approval.py` (5), `admin.py` (25 then; 32 now), `audit.py` (1), plus 9 endpoints added to
  `family.py` and 6 write endpoints added to `foundation.py` (`FOUNDATION_MANAGE`; 8 writes plus 4 member `propose` POSTs now) — **108
  endpoints at that point (137 at the v0.11.0 release, 201 now incl. Tier 6)**. New `nss_db_writer` PostgreSQL role (write access scoped to the
  auth/admin tables). `permission_master`/`role_permission` are seeded. Every Tier 4
  "verification"/demo seed file has been deleted — a fresh build produces **zero demo
  Person/Family/Membership data**; real data comes from the registration/approval flow or the
  single seeded admin superuser (`scripts/bootstrap_admin.py`, login `SS1`/`P1`). `tests/` was
  reorganized into `api/`, `db/`, `security/` and Playwright `ui/` suites around a
  session-scoped `SAVEPOINT`-per-module `conftest.py`. See `CLAUDE.md` and
  `docs/PROJECT_DOCUMENTATION.md` for the full, current detail — this bullet is a summary, not
  the source of truth.
* **Tier 6 — Governance (in progress, uncommitted on `feature/tier6-governance`):**
  10 new tables under `database/ddl/08_governance/` — `body_type_master`, `position_master`,
  `body_master`, `body_member_assignment`, `acting_position_assignment`, `election`,
  `election_nomination`, `election_vote`, `election_result`, `election_vote_participation` — plus
  `11_governance_immutability.sql` (ballot immutability trigger); seeds (8 body types, 10
  positions, 3 bodies) under `database/seed/08_governance/`. Membership gains
  `sakha_local_number_counter` and `membership_change_request` (Phase 7 is now 16 tables);
  `darshak_attendance_registration` v1.1 and `admin_scope` v1.1 (`ADVISORY_BOARD` scope) changed.
  Two new routers: `governance.py` (46 endpoints, `GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`) and
  `membership_change_request.py` (5 endpoints, Sakha Transfer / Apply for Darshak workflow) and
  `correspondence.py` (9 endpoints, Correspondence Register, `CORRESPONDENCE_VIEW`/`CORRESPONDENCE_MANAGE`) —
  **201 endpoints, 15 routers, 64 tables total**. New role `NSS_ERP_ADVISORY_BOARD_ADMIN`
  (auto-granted by `rbac_service.load_composite_grants`); 25 permissions (adds `CORRESPONDENCE_*`), 10 roles.

Current Focus:

* Tier 6 (Governance) implementation and verification on `feature/tier6-governance`, then merge
  to `develop`. Tier 5 (released as v0.11.0): still pending push of the local `v0.11.0` tag.
* Reconciling Solution-layer design docs with actual SQL/API implementation across all 22
  documented modules — every module has a complete (or largely complete) design, and seven
  groups have real SQL: Bootstrap RBAC (3 tables), Foundation (15), Organization (1), Person
  (2), Family (6), Membership (16), Authentication (5), Administration (2) and Governance (10) and Correspondence (4)
  — 64 tables.
  Released API/UI slices: Tier 0 (v0.6.0), Foundation (v0.7.0), Organization (v0.8.0), Person
  (v0.9.0), Family + Membership (v0.10.0, hotfixes through v0.10.4). The pytest suite has grown
  well beyond its v0.10.4 size (410 tests) — see `tests/README.md` for current counts and the
  per-file breakdown and fixture architecture.

---

# Tier-Wise Implementation Status

Each tier follows the vertical slice pattern: **DB -> API -> Web UI -> Flutter Mobile**.

| Tier | Modules | Focus | DB | API | Web UI | Mobile |
|------|---------|-------|----|-----|--------|--------|
| **0** | Bootstrap RBAC | Infrastructure bootstrap — `role_master`, `permission_master`, `role_permission` (3 tables) | Done | Done (4 endpoints) | Done (Bootstrap Verification) | -- |
| **1** | Foundation | Master data, geography, ID sequences, document/change-log (12 tables + `system_event_log`) | Done | Done (17 endpoints at release; 33 now) | Done (folded into `admin.html` Reference Data/Geography) | -- |
| **2** | Organization | Org types, statuses, self-referencing hierarchy (1 table; types/statuses sourced from Foundation `master_data`) | Done | Done (7 endpoints at release; 11 now) | Done (folded into `admin.html`) | -- |
| **3** | Person | Person identity, contact, address (2 tables: `person`, `person_address`) | Done | Done (4 endpoints at release; 5 now) | Done (folded into `admin.html` Person Directory) | -- |
| **4** | Family, Membership | Family groups/relationships + dynamic relationship graph (5 tables) + membership registration/approval/transfer/lifecycle (12 tables) | Done | Done (14 endpoints at release; 24 now incl. 9 Tier 5 Family endpoints) | Done (folded into `dashboard.html`/`admin.html`) | -- |
| **5** | Authentication, Administration | `user_account`, `password_history`, `registration_claim`, `password_reset_token`, `user_session`, `user_role`, `admin_scope` (5 auth + 2 admin tables, plus supporting tables added to Family/Membership/Foundation) — RBAC management, JWT, audit | Done (v0.11.0) | Done (auth, registration, claim-approval, admin, audit, geo-approval routers; 108 endpoints at release incl. Tier 1-4 additions) | Done (login/register/dashboard/admin pages) | -- |
| **6** | Governance (+ Membership change requests); Attendance, Assets & Property still planned | Unified body governance + elections (10 tables: `database/ddl/08_governance/`), Sakha Transfer / Apply for Darshak workflow; weekly puja attendance and property/asset custodianship not started | In progress (uncommitted; 10 governance tables + 2 membership tables) | In progress (`governance.py` 46 + `membership_change_request.py` 5 + `correspondence.py` 9 endpoints; 201 total) | In progress | -- |
| **7** | Heritage (Founder & Heritage) | Founder record, teachings, objectives, milestones, publications framework (8 tables) | Not started | Not started | Not started | -- |
| **8** | Programmes & Events | Common event framework (DRAFT, not frozen) — programme types, event instances, sessions | Not started | Not started | Not started | -- |
| **9** | Kumari Sangha, Kishor Puja, Sevak Sangha | Youth/seva modules — KM/KH identity, annual events, guardian assignment, SS transition, Sevak volunteer/training/seva | Not started | Not started | Not started | -- |
| **10** | Mahila Sangha | Mahila governance (unified body model) | Not started | Not started | Not started | -- |
| **11** | Publications, UPBS | Publication catalogue + UPBS event operations (registration, delegate cards, prasad patra) | Not started | Not started | Not started | -- |
| **12** | Finance | Financial transactions — Pranami, event fees, publication sales, property income (deliberately late, references upstream domains) | Not started | Not started | Not started | -- |
| **13** | Reports, Backup & Technical | Cross-cutting — reporting metadata/analytics, backup/restore records, technical administration | Not started | Not started | Not started | -- |

**Legend:**
- **Done** — implemented and merged to `develop`
- **Not started** — design docs complete, no implementation yet
- **--** — Mobile (Flutter) starts after Web UI stabilizes per tier; no mobile work planned until core tiers (0-5) have working web UIs

Tier ordering follows the unified build-order sequence (0–13). Tier 13 (Reports, Backup & Technical) is last because it is downstream of nearly every other module. Programmes & Events (Tier 8) remains DRAFT (not frozen) but provides common event infrastructure for the later programme modules, so it precedes them rather than coming last.

**Release convention:** one git tag per completed tier. Each tag is merged to `main` with a
release document under `docs/05_Releases/` before the next tier begins.

| Release | Tier | Scope |
|---------|------|-------|
| v0.6.0 | Tier 0 | Bootstrap RBAC — DB + API + UI + deployment (**released**) |
| v0.7.0 | Tier 1 | Foundation — API + Web UI + security hardening (DB already done) (**released**) |
| v0.8.0 | Tier 2 | Organization — API + Web UI (DB already done) (**released**) |
| v0.9.0 | Tier 3 | Person — DB rewrite + API + Web UI, plus the Organization master-data migration (**released**) |
| v0.10.0 | Tier 4 | Family + Membership — full vertical slice, family graph, Organization children-stats (**released**) |
| v0.10.1-v0.10.4 | Tier 4 (hotfixes) | Idempotent DDL/seed, Neon role bootstrap, performance indexes, a11y/perf polish (**released**) |
| v0.11.0 | Tier 5 | Authentication + Administration — full vertical slice (**released as v0.11.0**) |
| ... | Tier 6-13 | One tag per tier through Tier 13 (Tier 6 Governance is in progress) |

Next Release Target:

```text
Tier 6 Governance — unified body governance (bodies, positions, assignments, acting
assignments) + elections (nominations, ballots, results, vote participation), the
Sakha Transfer / Apply for Darshak change-request workflow, ADVISORY_BOARD admin scope.
(In progress on feature/tier6-governance; no version tag assigned yet.)
```

---

# Repository Structure

```text
NSS_ERP
│
├── api
│   ├── routers              (15 routers: bootstrap.py, foundation.py, organization.py, person.py, family.py, membership.py; plus, Tier 5 (v0.11.0): auth.py, admin.py, registration.py, claim_approval.py, audit.py, geo_approval.py; plus, Tier 6: governance.py, membership_change_request.py, correspondence.py)
│   ├── schemas               (bootstrap.py, foundation.py, organization.py, person.py, family.py, membership.py; plus, Tier 5: auth.py, admin.py, audit.py, geo_approval.py; plus, Tier 6: governance.py, membership_change_request.py)
│   ├── services              (family_graph.py — BFS relationship computation; plus, Tier 5: auth_service.py, rbac_service.py)
│   ├── dependencies          (Tier 5 — auth.py, rbac.py: FastAPI dependency-injected JWT/RBAC guards)
│   └── config.py, database.py, helpers.py, middleware.py, error_handlers.py, main.py
│
├── frontend                (login/register/dashboard/admin pages, served by FastAPI; the Tier 0-4 standalone verification pages were deleted and folded into admin.html/dashboard.html)
│   └── assets               (js/ — shared nss-*.js helpers, auth.js, org-dashboard.js + per-page files; css/ — badges.css, nss-layout.css, nss-datepicker.css, tailwind.min.css)
│
├── database
│   ├── ddl                  (00_bootstrap .. 05_membership; plus, Tier 5: 06_authentication, 07_administration; plus, Tier 6: 08_governance)
│   ├── seed                 (00_bootstrap .. 02_organization and 08_governance hold the SQL seeds, 03_person/04_family/05_membership hold only READMEs; 04_admin — the single admin superuser; demo/ — optional local-only demo seed run via RUN_DEMO_SEED)
│   └── scripts              (00_create_database.sql .. 06_setup_env.sh, 02_build.sh/.ps1, 03_validate.sh/.ps1, grant scripts)
│
├── scripts                (repo-root Python ops scripts, e.g. `bootstrap_admin.py`; distinct from `database/scripts/`)
│
├── tests                  (pytest suite: api/, db/, security/ integration tests + ui/ Playwright tests)
│
├── docs
│   ├── 00_Project_Governance
│   ├── 01_Authoritative_References
│   ├── 03_Solution
│   └── 05_Releases
│
├── BY-LAW                 (source PDFs/DOCX the docs/01_Authoritative_References transcripts come from)
├── NSS LOGO
├── CLAUDE.md
├── README.md
├── package.json, tailwind.config.js   (CSS build tooling only)
├── pytest.ini
├── render.yaml, render_build.sh
└── requirements.txt
```

See `docs/PROJECT_DOCUMENTATION.md` for the full, code-verified breakdown of each directory.

---

# Current Stable Version

```text
v0.11.0
```

Tier 5 Authentication + Administration (v0.11.0) — the latest release on `main` (tag created locally; push it
with `git push <remote> v0.11.0`). See `CLAUDE.md` and `docs/PROJECT_DOCUMENTATION.md` for current state.

---

# License

Internal NSS ERP Project

All Rights Reserved.
