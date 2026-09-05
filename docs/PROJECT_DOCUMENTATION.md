# NSS ERP — Project Documentation

> Comprehensive, code-verified documentation for the NSS ERP repository. This is the deep
> reference; `CLAUDE.md` is the terse AI-agent operating memory, and `README.md` is the
> public-facing project pitch. Where they disagree with what's actually in the code, this
> document (and the code itself) wins.

---

## Overview

NSS ERP is an in-development Enterprise Resource Planning system for **Nilachala Saraswata
Sangha (NSS)**, a religious/spiritual organization. It is not a generic corporate ERP — its
data model is built around NSS's own statutory structure (Kendra → Anchalika/Zilla →
Sakha), its membership system (Sangha Sevi ID), and organizational concepts like Family,
Governance, Attendance, Mahila Sangha, Kumari Sangha, Kishor Puja, Sevak Sangha, and Founder &
Heritage.

The project follows a **Constitution First → Governance → Requirements → Solution →
Implementation** philosophy, and for delivery, **Database First → API First → UI First**: raw
SQL schema is designed and frozen before Django models are written, and Django models before
UI. That philosophy is visible directly in the repo — the `person` and `organization` modules
both have hand-written SQL DDL that predates any Django migrations-as-source-of-truth story,
though several of Organization's own design decisions remain open (see Gotchas).

The codebase today is an early-stage skeleton: a working Django login + dashboard + person-list
flow, five real Django data models (`foundation`, `authentication`, `family`, `membership`,
`heritage`), a growing raw-SQL PostgreSQL schema (Bootstrap RBAC: 3 tables; Foundation: 12
tables; Organization: 3 tables — 18 tables implemented and committed in total, plus a
superseded Person prototype; see the `database/` detail below), and an extensive, mature
governance/documentation corpus that is significantly ahead of
the code. Solution-layer design documentation (`docs/03_Solution/modules/`) is complete or
near-complete across 22 module folders — with zero corresponding backend/SQL work beyond the
five Django apps and the Foundation/Organization DDL noted above. Two Solution-layer module
folders (`foundation`, `authentication`) share a name with an existing `backend/` Django app but
describe an entirely different scope/schema — see Conventions & gotchas.
`docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` states an `_id` business-identifier
convention that contradicts the project's actual frozen `_code`-only convention — see
Conventions & gotchas. `programmes_events` is the one module not tagged SOURCE ALIGNED (still
DRAFT, not frozen), though its cross-module reconciliation is complete.

## Architecture

```
Browser
   │
   ▼
Django Templates (Bootstrap 5, server-rendered)
   │
   ▼
Django Views (function-based only; no DRF/FastAPI wiring yet)
   │
   ▼
Django ORM  ──(parallel, not yet connected)──  raw SQL DDL (database/ddl/)
   │
   ▼
PostgreSQL
```

- **Web layer:** Django (`backend/`), server-rendered templates with Bootstrap 5. No FastAPI
  code exists yet despite `fastapi`/`starlette`/`uvicorn` being pinned in `requirements.txt` —
  they are currently unused dependencies (see Gotchas).
- **Data layer:** two parallel tracks that are not yet unified:
  1. **Django ORM models**, each app with its own `models.py` and migrations, using Django's
     default integer/auto PKs and the built-in `auth.User` for login (no custom user model).
  2. **Hand-written PostgreSQL DDL** under `database/ddl/`, following the project's own
     UUID-`_pk` + business-`_code` convention (see Conventions & Gotchas). This is the
     "real" intended schema per the governance/standards docs, but the Django apps do **not**
     read from or write to these tables — the two schemas currently describe overlapping but
     distinct designs for `Person`/`Organization` (e.g. Django's `foundation.Person` has
     auto-increment PK and a plain `gender` CharField; the SQL `person` table has a UUID PK,
     `person_code`, and a `gender_pk` FK to `gender_master`; Django's `foundation.Organization`
     has no hierarchy at all, while the SQL `organization` table is self-referencing).
- **Auth:** Django's built-in session auth + `django.contrib.auth.models.User`, function-based
  `login_view` (`backend/authentication/views.py`). No RBAC/JWT/OTP is implemented yet, even
  though `docs/00_Project_Governance/STD/05_security_standards.md` specifies a full RBAC +
  Row-Level-Security model.
- **Governance/documentation layer:** a large, independently-maintained set of governance
  standards (`docs/00_Project_Governance/`) and authoritative legal reference documents
  (`docs/01_Authoritative_References/`) that define the rules the eventual system must follow.
  This layer is far more mature than the code.

**Approved future direction (SOLUTION layer, not yet implemented in code):**
`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` is the authoritative technology decision
record and **supersedes the diagram above once code catches up** — it replaces Bootstrap 5 with
Tailwind CSS + DaisyUI + Alpine.js (HTMX retained), commits to actually wiring up FastAPI
(currently pinned-but-unused, see Gotchas), pins exact versions (Django 6.0.6, FastAPI 0.136.3),
and adds a hosting plan (Neon.dev for PostgreSQL, Render.com for the app). **Mobile strategy:**
the app's own mobile client is Flutter, targeting Android + iOS from day one (Hive/Drift for
offline local storage, syncing via a Dart background isolate, FCM for push). The web app itself
still uses IndexedDB/Service-Worker offline support for on-site event registration in the
browser — a parallel, not exclusive, path to the Flutter app.
`docs/03_Solution/architecture/DEVELOPER_REFERENCE_GUIDE.md` is a companion per-module "which
doc to read before coding" matrix across the REF→AUTH→GOV→REQ→SOLUTION→CODE chain. Until
`backend/` is actually migrated, treat everything in this "Architecture" section above as the
current CODE-layer reality and the Tech Stack Decisions doc as the approved target — don't
assume one from the other.

**Pre-DDL architecture gates (all FROZEN):**
`docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md` (`IMPLEMENTATION-TIER-001`,
12-tier build order across 22 modules) → `FK_DEPENDENCY_GRAPH.md` ("Gate 8" — physical FK
dependency graph across 86 frozen tables, topologically sorted into 8 depths with zero cycles,
resolves the audit-actor circular-dependency problem via a two-pass DDL strategy) →
`DDL_CREATION_ORDER.md` ("Gate 9" — the exact numbered `CREATE TABLE` sequence for all 86
tables plus the Pass-2 deferred-constraint list). Tiers 1-2 (Foundation, Organization) of the
12-tier order are executed — 15 tables live under `database/ddl/01_foundation/`/`database/ddl/
02_organization/` and their matching seed folders; Tiers 3-12 remain unimplemented. Note:
`IMPLEMENTATION_DEPENDENCY_ORDER.md`'s own closing status section (§79) reflects Tier 1
completion but hasn't been updated for Tier 2.

**`BOOTSTRAP_ARCHITECTURE.md`** (`SOL-ARCH-011`, FROZEN) defines a "Phase 0" that sits *before*
Tier 1: `role_master`/`permission_master`/`role_permission` have zero FK dependencies, so they
are created and seeded before Foundation — resolving the same audit-actor circular dependency
via the same two-pass strategy. It establishes `nss_admin` (PostgreSQL login, DDL-only) as
distinct from `NSS_ADMIN` (an ERP RBAC role, a `role_master` row) — the two are explicitly not
equivalent, and `NSS_ADMIN` never bypasses RBAC checks. DDL for all 3 tables exists under
`database/ddl/00_bootstrap/` and is **implemented and committed** (`feat(bootstrap): Phase 0
Bootstrap RBAC DDL and seed data`); seed data is partial (`role_master`: 8 roles;
`permission_master`/`role_permission`: empty, pending the permission catalogue). Ownership of
the 3 tables remains with Administration — "Bootstrap" is a DDL-sequencing label, not a new
module (see Gotchas).

## Tier-wise Implementation Plan

The system is built **vertically by tier**: each tier completes DB → API → UI before the
next tier begins. This is distinct from the DDL depth order (which is an internal database
concern within each tier's DB phase).

**Authority:** `docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md`
(`SOL-ARCH-008`, `IMPLEMENTATION-TIER-001`)

### Tier sequence

| Tier | Modules | Focus |
|-----:|---------|-------|
| 0 | Bootstrap | PostgreSQL bootstrap (database, roles, extensions, `nss` schema) + initial RBAC tables |
| 1 | Foundation | Common master/reference infrastructure (master_data, geography, sequences, settings) |
| 2 | Person + Organization | People identity (Sangha Sevi ID) and organizational hierarchy (Kendra → Anchalika/Zilla → Sakha) |
| 3 | Heritage | Founder biography, teachings, objectives, historical milestones, office bearers |
| 4 | Family + Membership | Family groups, membership types (Probationary/Regular/Associate), Sakha affiliation, local IDs, transfer |
| 5 | Authentication + Administration + Audit | User accounts, RBAC enforcement, organizational scopes, audit trail |
| 6 | Attendance + Governance + Assets & Property | Sangha Puja attendance, governance positions, immovable/movable property |
| 7 | Programme & Events | Event types, instances, sessions, registration (Janmotsaba, Rasoutsaba, etc.) |
| 8 | Kumari + Kishor + Sevak | Youth participation domains (Kumari/Kishor IDs, Seva architecture, Dina-Lipi, Niyam Panchak) |
| 9 | Mahila | Mahila-specific operations (not a separate membership category — Mahila Puja is Sangha Puja with majority women) |
| 10 | Publications + UPBS | Publication catalogue/operations, UPBS operational integration |
| 11 | Finance | Financial transactions (Pranami, event fees, publication sales, property income) — deliberately late, references upstream domains |
| 12 | Reports + Backup & Technical | Reporting, analytics, backup/restore, technical administration |

### Vertical slice per tier

Each tier follows the same internal sequence:

```
Database
  ├── Review frozen table design
  ├── DDL (CREATE TABLE in dependency-depth order)
  ├── Constraints + indexes
  ├── Seed data
  └── DB validation
       │
       ▼
API
  ├── Design + schemas
  ├── Endpoints
  └── Authorization
       │
       ▼
UI
  ├── Pages + forms
  ├── Tables + lists
  └── API integration
       │
       ▼
Integration test → freeze tier → next tier
```

### Key architectural facts per tier

**Tier 0 (Bootstrap):** PostgreSQL `nss_admin` role (database-level DDL owner) is distinct
from ERP `NSS_ADMIN` role (application RBAC row in `role_master`). Bootstrap RBAC tables
(`role_master`, `permission_master`, `role_permission`) are owned by the Administration
module — "Bootstrap" is a DDL-sequencing label, not a new module. Permission catalogue is
not yet frozen.

**Tier 2 (Person + Organization):** Person is the central human identity. The global Sangha
Sevi ID (e.g. `SS000001`) is permanent, unique across NSS, never changes, never reused.
Organization hierarchy: Kendra → Anchalika/Zilla → Sakha → Sakha Asana → Patha Chakra.
Nilachala Kutira and Smruti Mandira are separate roots, not children of Kendra. Organization
stores location inline (country, city_village, postal_code FKs + lat/long), no separate
`organization_address` table.

**Tier 4 (Family + Membership):** Membership is not the same as Sakha affiliation.
`membership_sakha_affiliation` carries effective-dated Sakha assignment. Transfer: old local
ID archived, new local ID issued, global Sangha Sevi ID unchanged. Local ID format:
`<3-5 char org code><8 digit sequence>` (e.g. `ESS00000123`).

**Tier 5 (Auth + Admin + Audit):** Effective access = User + Role + Permission +
Organizational Scope. Audit is separate from change history — `field_change_log` (Foundation)
handles field-level change tracking; `audit_master`/`system_event_log` handle security and
system events.

**Tier 6 (Attendance):** Membership Sakha ≠ Attendance Sakha. A member affiliated with
Sakha A can attend Sangha at Sakha B — the attendance record identifies the actual Sakha
where attendance occurred. Weekly Sangha Puja is owned by Attendance, not Programme & Events.
Attendance types: REGULAR, DARSHAK, VISITOR.

**Tier 6 (Assets & Property):** Legal owner, registered holder, and custodian are distinct
concepts. Covers acquisition, disposal, custody, maintenance, valuation, depreciation,
insurance, statutory obligations, restricted property.

**Tier 7 (Programme & Events):** Common structure: Programme Type → Event → Event Instance
→ Event Day → Event Session, plus Registration. Finance owns actual event financial
transactions. Attendance remains Attendance-owned.

**Tier 8 (Kumari/Kishor/Sevak):** These are not adult Membership categories. Kumari and
Kishor have separate identity/participation domains. Sevak architecture: Seva → Seva Head →
Application → Recommendation → Approval. Guardian model for minors includes
`guardian_sangha_sevi_pk`.

**Tier 11 (Finance):** Financial year 1 April – 31 March. Finance owns all actual
transactions. Other modules reference Finance — they do not create competing transaction
ledgers.

### Current position

Tier 0 (Bootstrap) and Tier 1 (Foundation) DB phases are **implemented**. Tier 2
(Organization) DB phase is **implemented**. Tier 2 (Person) DB phase is **pending** (the
`03_person/` DDL is a superseded prototype awaiting rewrite). All API and UI phases remain
**unimplemented** across all tiers.

### Database schema

All application tables live in the `nss` schema (`CREATE SCHEMA nss`). The `public` schema
is reserved for PostgreSQL extensions (pgcrypto, pg_trgm, btree_gin, postgis). The database
default `search_path` is set to `nss, public`. All DDL uses explicit `nss.` prefix on table
names, FK references, and index targets.

## Directory structure

```
NSS_ERP/
├── backend/                     Django project (see below)
├── database/
│   ├── ddl/                     Hand-written PostgreSQL schema, numbered by module
│   └── seed/                    Reference/lookup data matching the DDL
├── docs/
│   ├── PROJECT_DOCUMENTATION.md This file
│   ├── 00_Project_Governance/   AUTH/ GOV/ GDR/ STD/ — governance framework + engineering standards
│   ├── 01_Authoritative_References/
│   │   ├── NSS/            Source-faithful transcription of NSS's Constitution & Bye-Laws (see detail below)
│   │   └── MAHILA_SANGHA/  Source-faithful transcription of Mahila Sangha's own Bye-Law (see detail below)
│   ├── 02_Requirements/         Scaffolded only — business/functional/non_functional/traceability subfolders, no content yet
│   ├── 03_Solution/             Per-module design docs — 22 module folders (organization,
│   │                            person, membership, family, attendance, heritage, kumari,
│   │                            kishor, mahila, sevak, foundation, administration,
│   │                            authentication, governance, publications, reports, upbs,
│   │                            audit, backup_technical, finance, programmes_events,
│   │                            assets_property) + architecture/ui/infrastructure/standards/
│   │                            database/security content populated (see detail below); only
│   │                            api/ remains empty scaffolding
│   ├── 04_Testing/              Scaffolded only — unit/integration/api/ui/database/security/acceptance subfolders, no content yet
│   └── 05_Releases/             Release notes, v0.1.0 → v0.5.1
├── BY-LAW/                       Original source PDFs/docx of the NSS and Mahila Sangha Bye-Laws — the primary source both `docs/01_Authoritative_References/NSS/` and `.../MAHILA_SANGHA/` are transcribed from
├── requirements.txt              Python dependencies (pip, not pinned to a venv tool)
├── CLAUDE.md                     AI-agent operating memory/context (terse, instruction-oriented)
└── README.md                     Project pitch / high-level status
```

`database/scripts/` holds the executable bootstrap/build/validate scripts (`00_create_database.sql`,
`01_extensions.sql`, `02_build.sh`, `03_validate.sh`) that replaced the old repo-root `validate_foundation.sh`
(deleted) — see the `database/` detail below.

### `backend/` — Django project detail

```
backend/
├── config/            Django project config: settings.py, urls.py, asgi.py, wsgi.py
├── authentication/    Role, UserRole, LoginAudit models; login_view; wired into INSTALLED_APPS + urls
├── dashboard/         kendra_dashboard view only; NOT in INSTALLED_APPS but IS wired into urls.py (works because it has no models)
├── foundation/        OrganizationType, Organization, Address, Person models; person_list/person_detail views; wired into INSTALLED_APPS + urls
├── family/            FamilyGroup, FamilyMembership models; wired into INSTALLED_APPS; NO urls.py — unreachable via HTTP, admin-only
├── membership/        MembershipType, MembershipStatus, SanghaSevi models; wired into INSTALLED_APPS; NO urls.py — unreachable via HTTP
├── governance/        Stub only — empty models.py/views.py, no urls.py, not in INSTALLED_APPS
├── attendance/        Stub only — empty models.py/views.py, no urls.py, not in INSTALLED_APPS
├── heritage/          Founder singleton model (one-record-only, undeletable); wired into INSTALLED_APPS; NO urls.py — admin-only
├── static/            css/app.css (NSS color theme), js/app.js (empty placeholder)
├── templates/         base/ (base.html, login_base.html, navbar.html, sidebar.html), auth/, dashboard/, foundation/
└── manage.py
```

Modules referenced elsewhere in the project's roadmap (`mahila`, `kumari`, `kishor`, `sevak`,
`publications`, `upbs`, `reports`, `administration`) **do not exist yet** as Django apps — they
are planned, not scaffolded.

### `docs/01_Authoritative_References/NSS/` detail

Source-faithful transcription of the official NSS Bye-Law (`BY-LAW/NSS/NSS BYE-LAW.pdf`,
cross-checked against `BY-LAW/NSS/NSS_Bye_Law.docx`), organized by legal section:

```
NSS/
├── SECTION-A_PRELIMINARY_AND_GENERAL_PROVISIONS/   REF-001 — Name, Registered Office, Preamble, Objects, Memorandum of Association
├── SECTION-B_MEMBERSHIPS/                          REF-002 — Probationary/Regular/Associate Members, Cessation
├── SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA/    REF-003-C…009 — Governing Body, its Functions, and all 6 office-bearer duties;
│                                                    plus the two 1975 amendment Resolutions (REF-003-C(i)(2)-1975-01,
│                                                    REF-003-C(i)(8)-1975-02), filed adjacent to the clauses they amend
├── SECTION-D_ADVISORY_BOARD/                       REF-003-D
├── SECTION-E_GENERAL_BODY/                         REF-003-E
├── SECTION-F_FUNDS_OF_THE_KENDRA_SANGHA/           REF-003-F[A] (Funds), REF-003-F[b] (Maintenance), REF-003-F[c] (Utilisation) — 3 documents
├── SECTION-G_ACCOUNTS_AND_AUDIT/                   REF-003-G
├── SECTION-H_POWER_TO_AMEND/                       REF-003-H
└── SECTION-I_DISSOLUTION/                          REF-003-I
```

**No "Section J" exists in the source Bye-Law.** The Bye-Law's statutory sections end at
Section I (Dissolution); the two 1975 Resolutions that follow in the source text are explicit
amendments to Section C (inserting sub-clauses into Functions of the Governing Body and Duties
of the Secretary/Parichalak), not a standalone section. The content is filed as the two Section
C amendment documents above, not under an invented Section J.

Each REF document's clause-level numbering (numerals, letters, roman numerals) matches the
source exactly. `REF-001` additionally preserves the Memorandum of Association's
founding-members table (9 names + addresses), witnesses table, and the source's three distinct
certification/signature blocks (Memorandum, post-Dissolution, and post-Resolution) as separate,
non-deduplicated content, since all three appear separately in the source.

### `docs/01_Authoritative_References/MAHILA_SANGHA/` detail

Source-faithful transcription of the Nilachala Saraswata Mahila Sangha's own Constitution &
Bye-Law (`BY-LAW/NSS - Mahila Sangha/NSS Mahila Sangha By-Law.pdf`, cross-checked against
`BY-LAW/NSS - Mahila Sangha/NSS_Mahila_Sangha_Bye_Law.docx`) — a sibling folder to `NSS/`, not
nested under it, since Mahila Sangha is a separately registered entity with its own Bye-Law.
Uses a dedicated `REF-MS-XXX` identifier family (distinct from NSS's `REF-00X` family):

```
MAHILA_SANGHA/
├── SECTION-A_MEMORANDUM_AND_REGISTRATION/  REF-MS-MOA — Certificate of Registration, Memorandum, founding Governing Body + signatories + witnesses, historical 1989-1991 roster
├── SECTION-B_AIMS_AND_OBJECTS/             REF-MS-1
├── SECTION-C_MEMBERSHIP/                   REF-MS-2
├── SECTION-D_ENROLMENT_PROCEDURE/          REF-MS-3
├── SECTION-E_CESSATION_OF_MEMBERSHIP/      REF-MS-4
├── SECTION-F_CONSTITUTION_OF_THE_SANGHA/   REF-MS-5
├── SECTION-G_GOVERNING_BODY/               REF-MS-6(i)…6(viii) — Constitution, Powers & Duties, and all 6 office-bearer duties
├── SECTION-H_FUNDS/                        REF-MS-7(i)/(ii)/(iii) — Comprising/Maintenance/Utilisation, 3 documents mirroring NSS's own Funds-section split
├── SECTION-I_LEGAL_REPRESENTATION/         REF-MS-8
├── SECTION-J_AUDIT/                        REF-MS-9
├── SECTION-K_DISPUTE_SETTLEMENT/           REF-MS-10
├── SECTION-L_POWER_TO_AMEND/               REF-MS-11
└── SECTION-M_DISSOLUTION/                  REF-MS-12
```

22 documents total, all verified against source with clause numbering (numerals/letters/roman
numerals) preserved exactly as printed, including source quirks (no labeled "b)" sub-item in
Clause 6(ii); Clause 8 has no heading title at all — title assigned editorially). Every
REF-MS document's "Related Governance" section cites `AUTH-001` as the source defining the
`REF-MS` identifier family — `AUTH-001` defines it via `AUTH-ID-002A` and the Appendix B family
mapping, backed by `GDR-002`.

### `database/` detail

```
database/
├── scripts/              00_create_database.sql (superuser, postgres DB: creates nss_erp
│                         database + nss_admin/app_backend roles via dblink),
│                         01_extensions.sql (superuser, nss_erp: pgcrypto/pg_trgm/btree_gin),
│                         02_build.sh (runs all implemented DDL+seed in phase order),
│                         03_validate.sh (row-count/FK integrity checks) — replaced the
│                         old repo-root validate_foundation.sh
├── ddl/
│   ├── 00_bootstrap/     Implemented, committed — 3 tables: role_master,
│   │                     permission_master, role_permission (RBAC definitions, created
│   │                     before Foundation — zero FK dependencies; SOL-ARCH-011). Owned by
│   │                     Administration; see Gotchas for the role-catalogue discrepancy
│   ├── 01_foundation/    Implemented — 12 tables across 12 DDL files (02_master_category.sql
│   │                     … 13_city_village_postal_code_map.sql; extensions moved to scripts/):
│   │                     master_category, system_setting, id_sequence_master, country,
│   │                     document_master, field_change_log, master_data, state, district,
│   │                     city_village, postal_code, city_village_postal_code_map. Supersedes
│   │                     an older prototype (see `database/README.md` Superseded Artifacts)
│   ├── 02_organization/  Implemented — 3 tables: organization_type_master,
│   │                     organization_status_master, organization (self-referencing
│   │                     hierarchy, address inline, no `organization_address` table). Matches
│   │                     the frozen generic structure; `organization_code` naming/width/
│   │                     nullability and the seeded type codes don't yet match two separate
│   │                     frozen/design specs — see Gotchas
│   └── 03_person/        person_master_tables.sql (gender/marital_status/address_type masters), person.sql, person_address.sql — superseded prototype (uses per-domain masters, not the `master_data` pattern implemented in `01_foundation/`); will be replaced (see `feature/person-ddl`)
└── seed/
    ├── 00_bootstrap/     Partial — `role_master`: 8 roles seeded (includes `PATHA_CHAKRA_ADMIN`,
    │                     not listed in the frozen role catalogue — see Gotchas);
    │                     `permission_master`/`role_permission`: empty, pending the permission
    │                     catalogue
    ├── 01_foundation/    Implemented — 7 seed files: 11 master categories, ~40 master data
    │                     values (GENDER/MARITAL_STATUS/ADDRESS_TYPE/DOCUMENT_TYPE/
    │                     MEMBERSHIP_TYPE/MEMBERSHIP_STATUS/RELATIONSHIP_TYPE), 9 ID sequences
    │                     (PERSON zero-padded to 10 digits — see Gotchas), 5 countries, 112
    │                     states, ~770 districts (India only), 5 system settings
    ├── 02_organization/  Implemented — 8 organization types, 1 status master, 3 unique named
    │                     organizations (Kendra, Nilachala Kutira, Smruti Mandira)
    └── 03_person/        gender/marital_status/address_type seed rows — superseded prototype, seeds tables that don't exist in the new pattern
```

### `docs/03_Solution/` detail

```
03_Solution/
├── modules/
│   ├── organization/     01_module_overview/02_erd/03_lifecycle/04_business_rules/05_table_design (v1.1.0, GOVERNANCE ALIGNED); walks back the ANCHALIKA/ZILLA/SAKHA/PATHA_CHAKRA type-to-type parent matrix to an OPEN item — only the generic apex + self-referencing 3-table structure is frozen. Implemented in SQL, matching that generic structure — but the implemented `organization_code` column (VARCHAR(10), nullable) doesn't match `ORG-PENDING-001`'s frozen `organization_short_code` spec (VARCHAR(5), NOT NULL), and seeded type codes (`ANCHALIKA_SANGHA` etc.) don't match this doc's short forms (`ANCHALIKA` etc.) — see Gotchas
│   ├── person/            same pattern + README.md, v1.0.0 SOURCE ALIGNED, 5 files — **1 table** (`person` only — `document_master` is Foundation-owned); docs name the business identifier `person_id`, conflicting with the implemented DDL's `person_code` (see Gotchas); address/Aadhaar/photo/blood-group explicitly left OPEN despite `person_address` already existing in SQL
│   ├── membership/         01-05 overview/erd/lifecycle/business_rules/table_design, all DRAFT — richer than backend/membership/models.py (see Gotchas)
│   ├── family/             5 files, frozen 4-table design — richer than backend/family/models.py (see Gotchas)
│   ├── attendance/         6 files (business_rules/table_design/review_workflow at slots 04/05/06, FROZEN) + DARSHAK_BUSINESS_RULE.md (see below) — zero corresponding backend code
│   ├── heritage/           01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED — 8 tables designed (founder_master + teachings/objectives/milestones/publications/office-bearers + 2 lookup masters); `backend/heritage/` implements only founder_master, no urls.py
│   ├── kumari/             01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED (document-Status DRAFT) — KM000001 ID format; no backend/kumari/ app
│   ├── kishor/            01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 SOURCE ALIGNED (document-Status DRAFT) — KH000001 ID format + frozen v2.1 Guardian Model (Guardian must independently qualify via `sangha_sevi` identity); no backend/kishor/ app
│   ├── mahila/             01-05 overview/erd/lifecycle/business_rules/table_design, v2.1.0 — one body, two names (Mahila Governing Body = Mahila Parichalana Mandali); freezes the Mandali term at 2 years (MAH-040); no backend/mahila/ app
│   ├── sevak/              01-06 core sequence (only 06_table_design FROZEN, rest DRAFT/consolidation-in-progress) + sangha/, seva/, events/ subdocs; core SEV-001..040; no backend/sevak/ app
│   ├── foundation/         01-04 overview/erd/business_rules/table_design, v1.0.0 SOURCE ALIGNED — describes 10 tables: the original 8 (master_category, master_data, system_setting, id_sequence_master, country, state, district, city_village) plus `document_master` and `field_change_log`, Foundation-owned shared infrastructure (`DOC-ARCH-001`, `CROSS_MODULE_PRINCIPLES.md`). **Same name, different scope from `backend/foundation/`** (which implements Person/Organization/Address). **Implemented in SQL** — all 10 designed tables have DDL under `database/ddl/01_foundation/`, plus 2 more the design doc doesn't describe yet (`postal_code`, `city_village_postal_code_map`) — see Gotchas
│   ├── administration/     10 files (5 RBAC/Bootstrap docs + 1 Bootstrap RBAC column-level design + 4 Correspondence Register docs) — v1.0.0/v1.1.0 SOURCE ALIGNED — **8 Administration-owned tables**: the 5 RBAC tables (role_master, permission_master, role_permission, user_role, admin_scope — the first 3 also sequenced as "Phase 0 Bootstrap RBAC," `SOL-BOOT-001`/`SOL-ARCH-011`, DDL implemented and committed) plus 3 Correspondence Register tables (correspondence, correspondence_document, correspondence_finance_reference — `CORR-DECISION-003`); `user_account`/`password_history` are exclusively Authentication-owned per the Table Ownership Declaration; no backend/administration/ app. **Filename collision:** `06_bootstrap_rbac_table_design.md` and `06_correspondence_register_erd.md` share the same number — see Gotchas
│   ├── authentication/     Solution-layer "Authentication & Security", 5 files — v1.0.0 SOURCE ALIGNED — ERD still shows 7 tables, but exclusive ownership is only `user_account`+`password_history`; the other 5 RBAC tables are exclusively Administration-owned and appear here only for evaluation, not management. Argon2/JWT/session/Aadhaar-encryption/RLS as principles. **Different schema from** the real `backend/authentication/` Django app (Role/UserRole/LoginAudit) — same folder name, unreconciled designs
│   ├── governance/         Solution-layer ERP module, distinct from docs/00_Project_Governance/, 5 files — v1.0.0 SOURCE ALIGNED — Unified Body Governance Model (body_type_master, body_master, position_master, body_member_assignment, acting_position_assignment) + election entities (election, election_nomination, election_vote, election_result), 9 tables. **Freezes the Mahila Parichalana Mandali term at 3 years** (`04_governance_business_rules.md` GOV-BR-031) **and, per `03_governance_lifecycle.md`, a formal consensus→election→election-table reconstitution process** — both directly conflicting with mahila/'s own frozen **2-year** term (MAH-040) and its consensus-only reconstitution process; unreconciled, see Gotchas/Open questions. `backend/governance/` remains an empty stub
│   ├── publications/       7 files (overview/erd/business_rules/table_design/functional_design/ui_workflow/notification_purchase_design), v1.0.0 SOURCE ALIGNED + USER REQUIREMENTS — zero new tables, reuses Heritage's nss_publication/publication_type_master/publication_language_master; no backend/publications/ app
│   ├── upbs/               01-04, v1.0.0 SOURCE ALIGNED — 7 tables (upbs_event, upbs_registration, delegate_card, prasad_patra, accommodation_allocation, camp_master, guest_reference); Day 1/2/3 ops + volunteer structure explicitly PENDING; no backend/upbs/ app
│   ├── reports/            01-04, v1.0.0 SOURCE ALIGNED — 5 metadata/configuration-only tables (report_category_master, report_definition, report_filter_definition, dashboard, dashboard_widget); consumes but never duplicates other modules' data; no backend/reports/ app
│   ├── audit/              01-04, v1.0.0 SOURCE ALIGNED — 2 tables (audit_master, system_event_log); no backend/audit/ app
│   ├── backup_technical/   01-04, v1.0.0 SOURCE ALIGNED — 2 tables (backup_master, restore_history); no corresponding Django app
│   ├── finance/            01-05 design/erd/business_rules/table_design/lifecycle, v1.0.0 SOURCE ALIGNED (ERD tagged DRAFT — LOGICAL DESIGN) — 7 tables (financial_year, financial_scope, fund_master, financial_transaction, financial_receipt, financial_payment, financial_transfer); derives from REF-003-F[A]/[b]/[c] and REF-MS-7(i)-(iii); Financial Scope Independence principle (FIN-ARCH-001) keeps Financial Scope distinct from Organization; correctly follows the project's `_code` business-identifier convention (contrast with the `_id`/`_code` conflict below); business rules FIN-BR-001–068; no backend/finance/ app
│   ├── programmes_events/  Module #21, 01-05 overview/erd/lifecycle/business_rules/table_design, v0.1.0 DRAFT — the one module NOT tagged SOURCE ALIGNED; "ARCHITECTURALLY JUSTIFIED" per its cross-module review but "FORMAL MODULE FREEZE PENDING." Programme Type → Event Instance two-level model (Organization ≠ Event Location; Patha Chakra = Organization Type, not Event/Programme Type). **7 candidate common tables**: `programme_type`, `event`, `event_day`, `event_session`, `event_registration`, `event_location`, `event_history` — all cross-module reconciliation gates closed (`SOL-EVT-007`) but still none frozen DDL. Backed by 7 cross-module architecture docs — see `architecture/` below. No `backend/programmes_events/` app
│   └── assets_property/    Module #22, 01-05 overview/erd/lifecycle/business_rules/table_design, v1.0.0 DRAFT — SOURCE ALIGNED. Manages the physical/administrative record of NSS movable/immovable property and assets: `Property`/`Asset` as primary entities plus `Custodianship`, `Statutory Record`, `Maintenance Record`. 7 tables: `property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`. 74 business rules (`AP-001`–`AP-074`: 24 CONSTITUTIONAL, 32 ERP, 13 CROSS-MODULE, 5 PENDING). Depends only on Foundation + Person + Organization (no hard FK to Finance); sits at Tier 6 per `IMPLEMENTATION_DEPENDENCY_ORDER.md`. No `backend/assets_property/` app
├── standards/
│   └── lifecycle/         SOL-LIFE-001 (PARTICIPATION_LIFECYCLE_RULES.md), SOL-LIFE-002 (PERSON_LIFECYCLE_RULES.md), both FROZEN v1.0.0 — a SOLUTION-layer standards path distinct from the governance-layer docs/00_Project_Governance/STD/, not yet cross-referenced from either README or from the Sevak/Mahila/Kumari module docs that should cite SOL-LIFE-001 (see Gotchas)
├── architecture/
│   ├── README.md
│   ├── TECH_STACK_DECISIONS.md        v1.2 — approved SOLUTION-layer tech decision; Mobile Strategy (`TECH-MOB-001`, FROZEN — Flutter Android+iOS replaces PWA-first/Capacitor) — see Architecture section above
│   ├── DEVELOPER_REFERENCE_GUIDE.md   per-module "which doc to read before coding" matrix
│   ├── PROGRAMME_EVENT_DOMAIN_MODEL.md         (`SOL-EVT-001`) — domain model for Programmes & Events, feeding the `programmes_events` module
│   ├── EVENT_ENTITY_RECONCILIATION.md          (`SOL-EVT-002`) — reconciles that domain model against UPBS/Kishor/Sevak/Mahila/Finance/Attendance's own event-shaped entities
│   ├── MODULE_DEPENDENCY_MAP.md                (`SOL-ARCH-007`) — dependency map (hard FK/runtime/domain integrations), PROPOSED not frozen (v0.1.0); internally inconsistent on module count — its status footer says 22 modules (incl. Assets & Property), its own inventory table still lists only 21 rows
│   ├── IMPLEMENTATION_DEPENDENCY_ORDER.md      (`SOL-ARCH-008`), `IMPLEMENTATION-TIER-001` — 12-tier build order across all 22 modules, FROZEN (Assets & Property in Tier 6). Note: closing §79 status summary still reads DRAFT/v0.1.0/21-modules against the header/§44 — an internal inconsistency, not fixed here
│   ├── PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md (`SOL-EVT-006`), v1.1.0, FROZEN — final compatibility review for Module #21 against every other module; no hard conflicts; open ownership/migration-strategy risks it originally flagged were resolved by the file below
│   ├── CROSS_MODULE_PRINCIPLES.md              (`ARCH-CROSS-001`), v1.1.0, FROZEN — project-wide principles: one-owner-per-table, cross-module reference not duplication, Finance sole-owner of financial transactions, `DOC-ARCH-001` (document_master + field_change_log → Foundation), Correspondence Register decision. Carries 3 explicitly PENDING (not frozen) DDL-phase design notes: org short code, local Sakha number format, Visitor vs. Approved Darshak threshold
│   ├── FK_DEPENDENCY_GRAPH.md                  (`SOL-ARCH-009`), FROZEN — physical FK dependency graph ("Gate 8") across 86 frozen tables, topologically sorted into 8 depths, zero cycles; resolves the audit-actor circular-dependency problem via a two-pass DDL strategy
│   ├── DDL_CREATION_ORDER.md                   (`SOL-ARCH-010`), FROZEN — the exact numbered `CREATE TABLE` sequence for all 86 tables ("Gate 9") plus the Pass-2 deferred-constraint list
│   ├── BOOTSTRAP_ARCHITECTURE.md               (`SOL-ARCH-011`), FROZEN — Phase 0: creates/seeds `role_master`/`permission_master`/`role_permission` (zero FK deps) before Foundation; defines `nss_admin` (PostgreSQL login) ≠ `NSS_ADMIN` (ERP RBAC role); does not change SOL-ARCH-010's depth/sequence or claim table ownership (stays with Administration). Permission catalogue, bootstrap-admin Sangha Sevi identity, and MFA-controlled DB access (future `SOL-ARCH-012`) remain PENDING
│   └── PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md (`SOL-EVT-007`), FROZEN — closes all 7 P&E cross-module reconciliation gates; freezes `P&E-ARCH-001`/`002`; candidate table set settled at 7
├── database/
│   └── DATABASE_DESIGN_STANDARDS.md   (`SOL-DB-001`, DRAFT — SOURCE ALIGNED Consolidation) — cross-module DB conventions consolidated from module table-design docs: `_pk` UUID PK convention, audit columns, soft-delete, master-data architecture (generic `master_category`/`master_data` vs domain masters), module ownership boundaries (one owning module per table), cross-module FK principles, DDL build order sketch. **States a `_id` business-identifier convention (`person_id`, `organization_id`, `sangha_sevi_id`) that contradicts the project's already-frozen `_code`-only convention** — see Gotchas/Open questions
├── security/
│   └── SECURITY_ARCHITECTURE.md       (`SOL-SEC-001`, DRAFT — SOURCE ALIGNED Cross-Reference) — routing map only, no new rules: STD-05 (policy) → Authentication (identity/credentials) → Administration (RBAC) → Audit (logging) → per-module business rules (column-level sensitive-data handling); explicitly does not duplicate any rule already defined elsewhere
├── infrastructure/
│   └── DEPLOYMENT_SYNC_PLAN.md        Deployment/repository-sync plan
├── ui/
│   ├── README.md
│   └── mockups/           13 static HTML screens (Tailwind CSS + DaisyUI via CDN, no build step) + README.md; visual targets for Phase 4, not functional prototypes
└── (api/ still empty scaffolding — no FastAPI code exists in backend/ either)
```

`docs/03_Solution/modules/attendance/DARSHAK_BUSINESS_RULE.md` records an ERP implementation
decision (not derived from the Bye-Law): an earlier project Rule Book used "Darshak" as an
informal membership tier, but the actual Bye-Law (`REF-002`) has no such category — only
Probationary/Regular/Associate. "Darshak" is corrected to mean, operationally, either a
Probationary Member or a Regular Member visiting from another Sakha; it may appear as a UI
display label (dashboards, attendance screens) but must never be a `membership_type_master`
value in the database.

**Doc/code gap.** Membership, family, attendance, heritage, kumari, kishor, mahila, sevak,
administration, audit, authentication (Solution-layer), backup_technical, foundation
(Solution-layer), governance (Solution-layer), publications, reports, upbs, finance,
programmes_events, and assets_property all have Solution-layer design docs describing schemas
richer than what exists in code — none has a corresponding Django app except membership,
family, attendance (stub, no models), and heritage, whose actual models are far thinner than
their designs (`backend/membership/models.py` has 3 plain-PK models vs. ~10 UUID-keyed tables
in the design; `backend/family/models.py` has 2 models vs. a frozen 4-table design;
`backend/heritage/` implements only 1 of 8 designed tables). Don't assume any Solution-layer doc
describes currently running code.

## Setup & running

There is no documented setup script, Makefile, or `.env.example` in the repo — the steps below
are reconstructed directly from `backend/config/settings.py` and `requirements.txt`.

1. **Python dependencies:**
   ```
   pip install -r requirements.txt
   ```
   (Django 6.0.6, psycopg2-binary, django-environ, plus currently-unused fastapi/uvicorn/
   django-htmx/pillow — see Gotchas.)

2. **Database:** provision a PostgreSQL database; `database/scripts/01_extensions.sql`
   (run as superuser against nss_erp) enables `pgcrypto`, `pg_trgm`, and `btree_gin`.
   Run the DDL files under
   `database/ddl/` in numeric folder/file order (`00_bootstrap` — 3 RBAC tables, implemented
   and committed, seed data partial — → `01_foundation` — 12 tables — →
   `02_organization` — 3 tables, both implemented and seeded — → `03_person`, superseded
   prototype, skip it), then load `database/seed/` in the same order (see `database/README.md`
   for the exact `psql` invocations and full phase-by-phase execution table). `database/scripts/
   02_build.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]` runs all three implemented modules'
   DDL+seed end-to-end against a live Postgres instance, and `database/scripts/03_validate.sh`
   (same args) checks row counts and FK integrity afterward — these replaced the old repo-root
   `validate_foundation.sh` (Foundation-only, now deleted). Note this raw-SQL schema is **not**
   currently consumed
   by the Django app (see Architecture) — it exists independently, so setting it up is only
   required if you're working on the SQL/DB-first track rather than the Django app itself.

3. **Django environment file:** create `backend/.env` (read via
   `environ.Env.read_env(BASE_DIR / '.env')` at `backend/config/settings.py:21`) with:
   ```
   DB_NAME=...
   DB_USER=...
   DB_PASSWORD=...
   DB_HOST=...
   DB_PORT=...
   ```
   These five (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) are read with no
   defaults (`backend/config/settings.py:92-96`), so the app will fail to start without them.
   Note Django's own DB connection here is separate from any manual `psql` connection you'd use
   to run the DDL files in step 2 — they can point at the same or different databases today
   since nothing links them.

4. **Run migrations and start the server** (standard Django, from `backend/`):
   ```
   python manage.py migrate
   python manage.py createsuperuser   # to access /admin/
   python manage.py runserver
   ```

5. **Log in:** visit `/`, which redirects to `/login/` (`backend/config/urls.py:24-26`,
   `backend/authentication/urls.py`). After login you land on `/dashboard/`
   (`LOGIN_REDIRECT_URL` in `backend/config/settings.py:138`).

There is no test runner configured beyond Django's default (`manage.py test`); every app's
`tests.py` is an empty stub — **no tests exist in the repo today.**

## Configuration

| Setting | Source | Notes |
|---|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `backend/.env` (not committed, no `.env.example`) | Required, no defaults — `backend/config/settings.py:89-98` |
| `SECRET_KEY` | Hardcoded in `backend/config/settings.py:29` | Dev-only insecure key, not read from env — needs fixing before any real deployment |
| `DEBUG` | Hardcoded `True` — `settings.py` | No environment-based toggle yet |
| `ALLOWED_HOSTS` | Hardcoded `[]` — `settings.py` | Fine for local dev only |
| `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL` | `settings.py:137-139` | `/login/`, `/dashboard/`, `/login/` |
| `TIME_ZONE` | `settings.py` | `UTC`, `USE_TZ = True` |

No other configuration surface (feature flags, external service credentials, etc.) exists in
the code yet.

## Key workflows

### 1. Login → Dashboard
`GET /` → redirect to `/login/` (`backend/config/urls.py:24-26`) → `login_view`
(`backend/authentication/views.py:5`) renders `templates/auth/login.html`. On POST, Django's
`authenticate()`/`login()` run against the stock `User` model; success redirects (hardcoded
string `/dashboard/`, not `reverse()`) to `dashboard.kendra_dashboard`
(`backend/dashboard/views.py:4`), which renders `templates/dashboard/kendra_dashboard.html`
with no context. Failure re-renders the login page with an inline error message. Every login
attempt is **not** currently recorded to `authentication.LoginAudit` despite that model
existing — nothing in `login_view` writes to it yet.

### 2. Person listing/detail
`foundation.person_list` (`backend/foundation/views.py:7-24`, `@login_required`) queries
`Person.objects.filter(is_active=True).order_by("first_name")` and renders
`templates/foundation/person_list.html`. `foundation.person_detail`
(`views.py:26-40`) does `get_object_or_404(Person, pk=pk)` and renders
`templates/foundation/person_detail.html`. Both use Django's own `foundation.Person` model
(auto PK, plain `gender` CharField) — **not** the richer SQL `person` table in
`database/ddl/03_person/02_person.sql` (UUID PK, `person_code`, FK to `gender_master`). These
are two different, currently-unreconciled representations of "Person."

### 3. Person business-ID generation (SQL-schema track, not yet wired to Django)
`database/ddl/01_foundation/04_id_sequence_master.sql` defines an `id_sequence_master` table —
a registry of `{sequence_code, prefix, current_value, padding_length}` rows, seeded with **9**
sequences (`database/seed/01_foundation/03_id_sequence_master.sql`): `PERSON`→`P` (padding
**10** — first code is `P0000000001`, 11 characters), `SANGHA_SEVI`→`SS`, `ANCHALIKA`→`ANC`,
`ZILLA`→`ZL`, `SAKHA`→`SKH`, `SAKHA_ASANA`→`SA`, `PATHA_CHAKRA`→`PC`, `FAMILY`→`F`,
`DOCUMENT`→`DOC` (all padding 8 except `PERSON`). The five org-type-specific prefixes
correspond to the Organization module's frozen 8-type inventory (see Gotchas). This produces
IDs for the `person.person_code` column (`database/ddl/03_person/02_person.sql`, superseded
prototype, still uses an older 4-sequence/8-digit assumption) — **but** the current Person
module design doc (`docs/03_Solution/modules/person/05_person_table_design.md`, v1.0.0 SOURCE
ALIGNED) names this same business identifier `person_id`, not `person_code`. The doc and the
implemented DDL disagree on the column name; neither has been reconciled to the other yet. **No
SQL function or trigger and no Django code currently implements the increment/format logic** —
this table is pure configuration waiting on an implementation.

### 4. Organization hierarchy (designed; generic structure implemented in SQL)
`docs/03_Solution/modules/organization/01_organization_module_overview.md` through
`05_organization_table_design.md` (v1.1.0, GOVERNANCE ALIGNED) specify a self-referencing
`organization` table plus `organization_type_master` and `organization_status_master` — three
tables only, address inline on `organization` (no separate `organization_address` table).
**The specific Kendra → Anchalika/Zilla → Sakha → Patha_Chakra type-to-type parent matrix is
explicitly NOT frozen** — the business rules doc's §22 "Rules Explicitly Not Assumed" lists
both the exact parent-compatibility matrix and the exact `organization_type_master` seed values
as open items; only the generic apex + self-referencing structure is frozen. **Implemented in
SQL** at `database/ddl/02_organization/` — the 3-table structure matches the frozen design
exactly. Django's `foundation.Organization` model remains a much simpler placeholder (no
hierarchy, no self-reference) that predates this design and is unaffected by the SQL
implementation. Anyone picking up organization work should treat the design docs as the target
and the current Django model as a stand-in to be replaced — but should not assume the
type-hierarchy specifics are settled.
**Two freezes live outside this module's own doc set, not inside it:** (1) the business rules
doc's freeze of exactly **8 organization types** — `KENDRA`, `NILACHALA_KUTIRA`,
`SMRUTI_MANDIRA` (unique, fixed business code) plus `ANCHALIKA`, `ZILLA`, `SAKHA`,
`SAKHA_ASANA`, `PATHA_CHAKRA` (multiple, sequence-generated — `ANC`/`ZL`/`SKH`/`SA`/`PC`) — a
type *inventory* freeze, distinct from the still-open type-to-type parent matrix above; (2)
`ORG-PENDING-001`, an `organization_short_code` column (`VARCHAR(5)`, `UNIQUE`, `NOT NULL`)
frozen in `docs/03_Solution/architecture/CROSS_MODULE_PRINCIPLES.md` §20.1. **As implemented,
this column does not match that spec**: `database/ddl/02_organization/03_organization.sql`
defines it as `organization_code`, `VARCHAR(10)`, `UNIQUE`, **nullable** (comment: "3-5 chars,
unique") — different name, wider column, and nullable rather than required. Separately, the
seeded `organization_type_master` rows (`database/seed/02_organization/
01_organization_type_master.sql`) use `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA` as
business codes, not the short forms (`ANCHALIKA`/`ZILLA`/`SAKHA`) this module's own
business-rules doc uses (`SAKHA_ASANA`/`PATHA_CHAKRA` do match). See Gotchas and Open questions
for both.

## Conventions & gotchas

- **`_pk` vs business identifier suffix — actual convention differs from some docs.** The SQL
  DDL consistently uses `<entity>_pk` (UUID) for internal surrogate keys and `<entity>_code`
  (e.g. `person_code`, `country_code`, `sequence_code`) — never `_id` — for business/external
  identifiers. `CLAUDE.md` correctly documents this `_code` convention. Some newer
  SOLUTION-layer module docs (e.g. Person's table-design doc, `DATABASE_DESIGN_STANDARDS.md`)
  use `_id` in their own examples instead — that's a doc-side inconsistency, not a convention
  change; follow `_code` for new DDL.
- **Two parallel, unreconciled Person/Organization schemas.** See Architecture and Key Workflow
  #2/#4 above — don't assume the Django ORM models and the SQL DDL describe the same tables.
- **`dashboard`, `governance`, `attendance` are not in `INSTALLED_APPS`**
  (`backend/config/settings.py:39-51`). `dashboard` still works because `config/urls.py`
  includes its urlconf directly and it has no models to register; `governance`/`attendance` have
  no URLs at all and are pure stubs (empty `models.py`/`views.py`, no `urls.py`).
  `family`/`membership` have real models but no `urls.py` — reachable only via `/admin/` (and
  only `membership`'s admin is registered). `heritage` is in the same boat: real model
  (`Founder`), admin-registered, but no `urls.py`.
- **Dead links in the UI.** `backend/templates/base/sidebar.html` links "Members" and
  "Families" to `href="#"` — no URL exists for either yet, consistent with the missing
  `urls.py` files above.
- **Orphan/empty files.** `backend/templates/dashboard/sakha_dashboard.html` and
  `backend/static/js/app.js` are both 0 bytes — present as placeholders, not implemented.
- **Unused dependencies in `requirements.txt`.** `fastapi`, `starlette`, `uvicorn`,
  `annotated-doc`, `anyio`, `h11`, `django-htmx`, and `pillow` are pinned but have zero usage
  in `backend/` today (no FastAPI app, no `hx-` template attributes, no `ImageField`). Don't
  assume their presence means those integrations exist.
- **Governance/standards docs are far ahead of the code.** `docs/00_Project_Governance/STD/`
  (naming conventions, audit standards, security standards, master data catalog) describes a
  mature target architecture (RBAC tables, RLS, full audit trail with `*_by_sangha_sevi_pk`
  columns, etc.) that the current `backend/` code does not yet implement — the built-in
  `auth.User` model and hardcoded dev settings are a long way from that target. Treat the STD
  docs as the destination, not the current state.
- **Person module docs vs. Organization module docs.** Both are partially implemented, and both
  disagree with their own SQL on naming — don't confuse "documented" with "built" for either.
  Person's design (`docs/03_Solution/modules/person/`, v1.0.0 SOURCE ALIGNED) is *partially*
  implemented in SQL (`database/ddl/03_person/` has `person` and `person_address`, though that
  whole track is itself superseded — see the `database/` detail above) but disagrees with the
  DDL on the business-identifier column name (`person_id` in the docs vs. `person_code` in SQL —
  see Key Workflow #3). Person's design used to describe a second table, `document_master`, but
  that was reassigned to Foundation (`DOC-ARCH-001` — see the Gotcha below); Person is now a
  1-table design (`person` only). Organization's generic 3-table structure **is** implemented in
  SQL and matches the design — but the implemented `organization_code` column doesn't match the
  frozen `ORG-PENDING-001` spec (`organization_short_code`, `VARCHAR(5)`, `NOT NULL` vs. the
  actual `VARCHAR(10)`, nullable `organization_code`), and the seeded organization-type codes
  don't match the design docs' short forms — see Key Workflow #4.
- **No tests.** Every Django app's `tests.py` is the default empty stub.
- **Git remotes.** `git remote -v` shows two remotes: `personal`
  (`github.com/sandeeppanda22/NSS_ERP`, daily dev) and `org`
  (`github.com/NilachalaSaraswataSangha/NSS_ERP`, the production/deploy target).
  `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` §6 uses the `org` alias consistently
  in its Production remote and Flow rows.
- **Second "standards" location.** `docs/03_Solution/standards/lifecycle/` (`SOL-LIFE-001`/
  `PARTICIPATION_LIFECYCLE_RULES.md`, `SOL-LIFE-002`/`PERSON_LIFECYCLE_RULES.md`) is a distinct
  path from the pre-existing governance-layer `docs/00_Project_Governance/STD/` — both are
  legitimately different layers (SOLUTION vs. GOV per the lifecycle described in `CLAUDE.md`).
  It has its own `README.md` explaining the two documents and their relationship, but neither
  `STD/README.md` nor any top-level doc cross-references the other standards location, and the
  Sevak/Mahila/Kumari module business-rules docs don't yet cite `SOL-LIFE-001` even though its
  own text says they should reference it rather than duplicate its rules.
- **Two Solution-layer module folders share a name with an existing `backend/` Django app but
  describe unrelated schemas.** `docs/03_Solution/modules/foundation/` (describes 10 tables:
  the original 8 master data/geography/sequence tables plus `document_master` and
  `field_change_log`) is **not** the same thing as the `backend/foundation/` app (which
  implements Person/Organization/Address — those live in the separate `person/`/`organization/`
  Solution folders instead). The implemented `database/ddl/01_foundation/` has 12 tables, 2 more
  than this design doc describes (`postal_code`, `city_village_postal_code_map`) —
  implementation is ahead of the design doc for those two, see the Foundation Gotcha below.
  Likewise `docs/03_Solution/modules/authentication/` (ERD still shows 7 tables, but exclusive
  ownership is only `user_account`+`password_history`; the other 5 RBAC tables are exclusively
  owned by `administration/`) is **not** the same schema as the real `backend/authentication/`
  app (`Role`, `UserRole`, `LoginAudit`). Don't assume either Solution doc set describes the
  Django app of the same name.
- **`document_master` is Foundation-owned; RBAC table ownership is split between Authentication
  and Administration** (`CROSS_MODULE_PRINCIPLES.md`, `ARCH-CROSS-001`, FROZEN). `DOC-ARCH-001`
  establishes Foundation as the sole owner of a common `document_master` document registry
  (Person, Heritage, and Publications are consumers via FK, not owners) and a Foundation-owned
  `field_change_log` table for business-significant field-level change tracking, distinct from
  each module's own `_history` tables. Separately, a Table Ownership Declaration makes
  `user_account`/`password_history` exclusively Authentication-owned and the 5 RBAC tables
  (`role_master`, `permission_master`, `role_permission`, `user_role`, `admin_scope`)
  exclusively Administration-owned — both modules may FK to the other's tables but neither
  co-owns them. `role_master`/`permission_master`/`role_permission` are additionally sequenced
  as "Phase 0 Bootstrap RBAC" (`SOL-BOOT-001`, `BOOTSTRAP_ARCHITECTURE.md`/`SOL-ARCH-011`) —
  created before Foundation for DDL-ordering reasons; ownership doesn't change. This document
  also carries 3 explicitly **PENDING — DDL phase** design notes
  (not covered by its own FROZEN status): `ORG-PENDING-001` (organization short code, 3–5
  letters), `MEM-PENDING-001` (local Sakha number format, plus a proposed three-level Sangha
  Sevi → Sakha Affiliation → Local Number identity chain — the current
  `membership_transfer_history.old_local_sakha_number`/`new_local_sakha_number` VARCHAR fields
  are documented as insufficient for it), and `ATT-PENDING-001` (Visitor vs. Approved Darshak
  threshold — classified as an ERP operational refinement, not source-derived; no counter
  column planned, the threshold is meant to be derivable from existing attendance records).
- **Administration owns a Correspondence Register** (`CORR-DECISION-003`, `CORR-ARCH-001`/
  `002`, all FROZEN) — a generic inward/outward official-communication register
  (`correspondence`, `correspondence_document`, `correspondence_finance_reference`). Explicitly
  not a generic application/workflow engine and not an owner of the underlying business matter
  (membership renewals, property matters, governance decisions stay with their respective
  modules) or of financial transactions (Finance remains sole owner per `FIN-ARCH-001`; the
  Finance link is a reference-only M:N junction). One rule (`CORR-BR-018`, the
  `relationship_type` candidate values) is explicitly PENDING until Finance's own transaction
  taxonomy is frozen.
- **Mahila Parichalana Mandali term length disagrees across two frozen module docs.**
  `docs/03_Solution/modules/governance/04_governance_business_rules.md` (GOV-BR-031, "Mahila
  3-Year Term | FROZEN") sets the Mandali's term at **3 years**;
  `docs/03_Solution/modules/mahila/04_mahila_business_rules.md` (MAH-040, "Two-Year Term")
  freezes it at **2 years**. Both are marked FROZEN in their own module. Flagged here, not
  resolved, since picking a winner is a design decision this pass shouldn't make unilaterally.
- **`DATABASE_DESIGN_STANDARDS.md` states a business-identifier convention that contradicts the
  project's own frozen convention.** §6/§15/§21 of `docs/03_Solution/database/
  DATABASE_DESIGN_STANDARDS.md` (`SOL-DB-001`) define `_id` as the suffix for "sequential
  business identifiers" (`person_id`, `organization_id`, `sangha_sevi_id`), reserving `_code`
  for "stable classification codes" only. This directly contradicts the actual implemented SQL
  (`database/ddl/03_person/02_person.sql` uses `person_code`, not `person_id`) and the
  correction already recorded in `CLAUDE.md`. This document's own source-inventory list of
  module table-design docs suggests it absorbed the newer module docs' inconsistent `_id` usage
  (the same `person_id`/`person_code` conflict tracked for the Person module) rather than the
  actual frozen DDL convention — worth a human decision on which document is wrong before any
  new DDL is authored against `SOL-DB-001`'s stated convention.
- **Six lifecycle documents restate Person-death-cascade rules instead of citing the existing
  lifecycle standards.** `person/03_person_lifecycle.md` (SOL-PER-005),
  `family/03_family_lifecycle.md` (SOL-FAM-005), `governance/03_governance_lifecycle.md`
  (SOL-GOV-005), `attendance/03_attendance_lifecycle.md` (SOL-ATT-006),
  `authentication/03_authentication_security_lifecycle.md` (SOL-AUTH-005), and
  `administration/03_administration_lifecycle.md` (SOL-ADMIN-005) each independently restate
  near-identical death-effect language, but none cites
  `docs/03_Solution/standards/lifecycle/PERSON_LIFECYCLE_RULES.md` (SOL-LIFE-002) or
  `PARTICIPATION_LIFECYCLE_RULES.md` (SOL-LIFE-001) as authority, even though SOL-LIFE-001 §16
  explicitly says modules "shall reference this standard rather than duplicating these rules."
  Content doesn't contradict SOL-LIFE-002 for the modules already in its consequence table
  (governance/family/attendance match it); Authentication and Administration aren't in that
  table at all, so their "not automatically deactivated" stance is a genuine gap in
  SOL-LIFE-002 rather than a contradiction. Not fixed here — editing six lifecycle docs' rule
  text is a content decision, not a drift correction.
- **Governance's and Mahila's lifecycle docs disagree on more than just term length.** Beyond
  the already-tracked 3-year vs. 2-year Mandali term conflict,
  `governance/03_governance_lifecycle.md` §33 models Mahila reconstitution as a formal
  consensus-attempt → election → `election`/`election_result`-table process, while
  `mahila/03_mahila_lifecycle.md` §24–26 describes routine reconstitution as Parichalak
  consensus + President's consent with no formal election tables at all, reserving actual
  elections for President/Vice-President vacancies only. Neither lifecycle doc reconciles this
  against the other.
- **`programmes_events/` (Module #21) is not source-aligned like its siblings, but its
  cross-module reconciliation is complete.** Unlike every other module (tagged `v1.0.0 DRAFT —
  SOURCE ALIGNED`), `programmes_events/` is v0.1.0, explicitly "FORMAL MODULE FREEZE PENDING,"
  and none of its candidate tables are frozen DDL. Its candidate-table set (`programme_type`,
  `event`, `event_day`, `event_session`, `event_registration`, `event_location`,
  `event_history`) is settled — `PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md` (`SOL-EVT-007`)
  closed all 7 gates the cross-module review had left open, including the "Ownership Ambiguity"
  risk (resolved: UPBS/Kishor/Sevak's own event entities become common-Event extensions, not
  left standalone or merely referenced) and confirming Weekly Sangha Puja stays
  Attendance-owned with no P&E dependency. Reconciliation being complete is not the same as the
  module being frozen — don't cite any table name as settled yet.
- **Mobile strategy is Flutter, not PWA.** `TECH_STACK_DECISIONS.md` §4 (`TECH-MOB-001`,
  FROZEN) targets Android + iOS from day one (Hive/Drift for offline storage, FCM for push) —
  supersedes an earlier PWA-first/Capacitor position. If any older doc or memory still says
  "PWA" for the mobile client specifically, treat it as superseded — the web app's own
  IndexedDB/Service-Worker offline support for browser-based on-site registration is unaffected
  and remains a parallel path.
- **`assets_property/` (Module #22) is the physical/administrative record of NSS property and
  assets** — `Property`/`Asset` as primary entities plus `Custodianship`/`Statutory Record`/
  `Maintenance Record`, 7 tables, 74 business rules. Tagged `v1.0.0 DRAFT — SOURCE ALIGNED`
  like most other modules (unlike Programmes & Events). Explicitly does not own financial
  transactions/depreciation (Finance), acquisition/disposal approval (Governance), or
  historical/cultural significance (Heritage) — those modules may reference the same physical
  entity without duplicating records. One rule (`AP-066`, whether "sacred articles" fall under
  this module or Heritage's model) is explicitly PENDING.
- **Two pre-DDL architecture "gates" sit on top of the 12-tier build order**
  (`SOL-ARCH-009`/`010`). `FK_DEPENDENCY_GRAPH.md` topologically sorts all 86 frozen tables into
  8 dependency depths (zero cycles) and resolves the audit-actor circular-dependency problem
  (`sangha_sevi` needed for audit columns everywhere, but itself depends on Foundation) via a
  two-pass DDL strategy: create tables without audit-actor FKs first, add those constraints in
  a second pass. `DDL_CREATION_ORDER.md` turns that into the exact numbered `CREATE TABLE`
  sequence. Tiers 1-2 (Foundation, Organization) have been executed against `database/ddl/`;
  Tiers 3-12 have not. `BOOTSTRAP_ARCHITECTURE.md` (`SOL-ARCH-011`) adds a "Phase 0" ahead of
  Tier 1 for the 3 RBAC tables — DDL is implemented and committed. The 7 Programmes
  & Events candidate tables are explicitly listed in both
  but marked NOT EXECUTABLE pending that module's own formal freeze.
- **Role catalogue discrepancy between the frozen design docs and the actual Bootstrap RBAC
  DDL/seed.** `05_administration_table_design.md` §8.7 and `SOL-BOOT-001` §4.2 both describe 7
  roles / 4 scope levels (`KENDRA`/`ANCHALIKA`/`ZILLA`/`SAKHA`). The actual
  `database/ddl/00_bootstrap/01_role_master.sql` CHECK constraint and
  `database/seed/00_bootstrap/02_role_master.sql` seed data implement 8 roles / 5 scope levels,
  adding `PATHA_CHAKRA_ADMIN`/`PATHA_CHAKRA`. Neither design doc has been updated to match.
- **`app_backend` PostgreSQL role is referenced but never defined.** `database/README.md`'s
  header names `app_backend` as the "Runtime Read/Write" role, alongside `nss_admin` ("DDL
  Execution Authority") — but `BOOTSTRAP_ARCHITECTURE.md` (`SOL-ARCH-011`) only formalizes the
  `nss_admin`/`NSS_ADMIN` distinction and never mentions `app_backend` by name. No document
  currently defines what privileges `app_backend` has.
- **Filename collision in `docs/03_Solution/modules/administration/`.**
  `06_bootstrap_rbac_table_design.md` (`SOL-BOOT-001`) and `06_correspondence_register_erd.md`
  (`SOL-ADMIN-006`) share the same leading number — not renamed here, flagging only.

## Open questions / TODOs

- **Reconcile Django ORM models with the SQL DDL schema** for `Person` and `Organization`
  (or decide the SQL DDL track supersedes the current Django models and plan a migration).
- **Reconcile `person_id` (design docs) vs. `person_code` (implemented SQL)** — the Person
  table design doc names the business identifier `person_id`; the actual DDL column is
  `person_code`. See Key Workflow #3.
- **Decide the Organization type-to-type parent matrix** (which org types may parent which —
  e.g. does ANCHALIKA/ZILLA sit under KENDRA, does PATHA_CHAKRA sit under SAKHA or KENDRA) —
  the v1.1.0 GOVERNANCE ALIGNED business rules doc explicitly left this open rather than
  freezing it; do not treat any specific matrix as decided until this is resolved.
- **Decide the Person address/Aadhaar/photo/blood-group model** — the v1.0.0 SOURCE ALIGNED
  Person docs explicitly leave these open, even though `database/ddl/03_person/03_person_address.sql`
  already implements a multi-address `person_address` table. Don't treat the SQL as a de facto
  frozen decision without reconciling it against the docs' "OPEN" framing.
- **Implement the `id_sequence_master` increment/formatting logic** (no function, trigger, or
  Django code currently does this — see Key Workflow #3).
- **Implement the Founder & Heritage schema beyond `founder_master`** — the v1.0.0 design
  (`docs/03_Solution/modules/heritage/`) specifies 8 tables; `backend/heritage/` only implements
  1 (`founder_master`).
- **Wire up `family`, `membership`, and `heritage` URLs/views** — models exist, nothing is
  reachable over HTTP yet.
- **Decide the fate of `governance` and `attendance` apps** — currently pure stubs, not even in
  `INSTALLED_APPS`.
- **Add `family` to Django admin** — currently the only real-model app not registered.
- **Record login attempts** — `authentication.LoginAudit` model exists but `login_view` never
  writes to it.
- **Wire up the unused `fastapi`/`starlette`/`uvicorn`/`django-htmx`/`pillow` dependencies** —
  per `TECH_STACK_DECISIONS.md`, FastAPI is decided to be actually used for JSON APIs/sync
  endpoints, served via Uvicorn alongside Django. Not yet implemented in code.
- **Migrate frontend from Bootstrap 5 to Tailwind CSS + DaisyUI + Alpine.js** per the same
  decision doc — `backend/templates/` still use Bootstrap 5 (see Architecture above); the 13
  mockups under `docs/03_Solution/ui/mockups/` are the visual target, not yet built into
  Django templates.
- **No `.env.example`** — new contributors have to reverse-engineer required env vars from
  `settings.py`; consider adding one.
- **`docs/02_Requirements/` and `docs/04_Testing/` are empty scaffolding** — folder structure
  exists (per `AUTH-001`/`GOV-003` repository architecture) but no actual requirements or test
  documentation has been written yet.
- **`ORG-PENDING-001` (organization short code) is frozen in `CROSS_MODULE_PRINCIPLES.md` but
  never propagated into the Organization module's own doc set.** None of
  `docs/03_Solution/modules/organization/{01_organization_module_overview,02_organization_erd,
  04_organization_business_rules,05_organization_table_design}.md` or that module's own
  `README.md` mention `organization_short_code`, `ORG-PENDING-001`, or `VARCHAR(5)` anywhere —
  the frozen column exists only in the cross-module architecture doc, not in the module that
  will actually own the column. Flagged, not fixed, since adding the column to the module's own
  design docs is itself a design-doc edit, not a drift correction.
- **Three DDL-phase design notes (`CROSS_MODULE_PRINCIPLES.md` §20-21):** `ORG-PENDING-001`
  (organization short code format, 3–5 letters) — FROZEN. `MEM-PENDING-001` (local Sakha number
  format + a proposed three-level Sangha Sevi → Sakha Affiliation → Local Number identity chain
  — likely needs a dedicated entity rather than the current inline VARCHAR fields) — PENDING.
  `ATT-PENDING-001` (Visitor vs. Approved Darshak threshold, classified ERP-operational not
  source-derived) — PENDING, non-blocking. `CORR-EXT-001` (organization-scoped correspondence
  reference numbering) — FROZEN, unblocked by the `ORG-PENDING-001` freeze. Correspondence
  format is `<ORG_SHORT_CODE>/IN/YYYY-YY/NNN` (per-organization sequences).
- **Reconcile the implemented `organization_code` column with the frozen `ORG-PENDING-001`
  spec.** `database/ddl/02_organization/03_organization.sql` defines `organization_code
  VARCHAR(10) NULL`; `ORG-PENDING-001` (`CROSS_MODULE_PRINCIPLES.md` §20.1) froze
  `organization_short_code VARCHAR(5) NOT NULL`. Different column name, different width,
  different nullability — needs an explicit decision on whether the DDL should be altered to
  match the frozen spec, or the spec updated to match what was actually built. See Key Workflow
  #4/Gotchas.
- **Reconcile seeded organization-type codes with the design docs' short forms.**
  `database/seed/02_organization/01_organization_type_master.sql` seeds
  `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA`; the Organization module's own business rules
  doc uses the short forms `ANCHALIKA`/`ZILLA`/`SAKHA` (`SAKHA_ASANA`/`PATHA_CHAKRA` already
  match). Needs a decision on which form is authoritative before this seed data or the design
  docs are extended further.
- **Resolve whether the two top-level `database/ddl/README.md`/`database/seed/README.md`
  files should keep existing at all.** `database/README.md`'s own execution-order section
  already covers everything they cover, via the per-module READMEs — they may be redundant
  duplication that will drift again next time a module lands. Not resolved here since deleting
  them is a structural decision, not a drift correction.
- **Reconcile `04_foundation_table_design.md`/the Foundation ERD with the implemented
  `postal_code`/`city_village_postal_code_map` tables** — these 2 tables exist in
  `database/ddl/01_foundation/` but aren't described in the Foundation module's own design docs
  (which describe 10 tables, not the 12 implemented).
- **One Correspondence Register rule is PENDING** — `CORR-BR-018`'s `relationship_type`
  candidate values for `correspondence_finance_reference` are deferred until Finance's own
  transaction taxonomy is frozen.
- **One Assets & Property rule is PENDING** — `AP-066`, whether "sacred articles" fall under
  this module's Asset-custody model or Heritage's cultural-significance model, is unresolved.
- **Formal Module #21 (Programmes & Events) freeze is the one remaining step for that module** —
  its cross-module reconciliation is complete and its candidate table set is settled at 7, but
  the module overview doc and its own README were never bumped past v0.1.0/DRAFT, and none of
  its 7 tables are frozen DDL. Reconciliation-complete is not the same as module-frozen.
- **Resolve the Mahila Parichalana Mandali term-length conflict** —
  `governance/04_governance_business_rules.md` freezes 3 years,
  `mahila/04_mahila_business_rules.md` freezes 2 years; their lifecycle docs also disagree on
  the reconstitution process itself (formal election tables vs. consensus-only). Needs an
  explicit decision on which module doc is authoritative (or a joint correction to both) before
  either is implemented — see Gotchas.
- **Decide whether to rename one side of the `foundation`/`authentication` naming collisions**
  — the Solution-layer `docs/03_Solution/modules/foundation/` and `.../authentication/` module
  folders describe different schemas than the identically-named `backend/foundation/` and
  `backend/authentication/` Django apps. Not urgent (the doc folders are internally consistent
  and cross-reference the collision), but worth a deliberate naming decision before more code or
  docs are added under either name.
- **Add `SOL-LIFE-001`/`SOL-LIFE-002` cross-references to the six lifecycle docs** that
  currently restate death-cascade rules instead of citing them (`person`, `family`,
  `governance`, `attendance`, `authentication`, `administration`) — a future pass could add
  cross-reference notes without changing any rule content.
- **Decide which document is authoritative for the business-identifier suffix** —
  `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` (`_id`) or the implemented SQL DDL +
  `CLAUDE.md` (`_code`). Needs an explicit correction to `SOL-DB-001` (or a project-wide
  convention change, which seems unlikely given how much existing SQL/documentation already
  uses `_code`).
- **Reconcile the frozen role catalogue with the actual Bootstrap RBAC implementation** —
  `05_administration_table_design.md` §8.7 and `SOL-BOOT-001` §4.2 describe 7 roles / 4 scope
  levels; the actual DDL CHECK constraint and seed data implement 8 roles / 5 scope levels,
  adding `PATHA_CHAKRA_ADMIN`. Needs a decision on whether to add Patha Chakra to the frozen
  docs or trim it back out of the DDL/seed. See Gotchas.
- **Define the `app_backend` PostgreSQL role** — named in `database/README.md`'s header as the
  runtime read/write role, but no document specifies its actual privileges (table-level grants,
  RLS interaction, etc.). See Gotchas.
- **Resolve the `06_bootstrap_rbac_table_design.md`/`06_correspondence_register_erd.md`
  filename collision** in `docs/03_Solution/modules/administration/` — both are numbered `06`.
  See Gotchas.
- ~~**Fix `database/scripts/03_validate.sh`'s `id_sequence_master` duplicate check**~~ — **FIXED.**
  Changed from `entity_name` to `sequence_code`.
- **Reconcile `database/ddl/01_foundation/README.md`'s Design Decisions section with the actual
  `organization` table.** It states Organization stores `postal_code_pk` (FK to `postal_code`)
  plus `latitude`/`longitude` `NUMERIC(10,7)` — but the implemented `organization` table
  (`database/ddl/02_organization/03_organization.sql`) has only a plain-text `postal_code
  VARCHAR(20)` column and no `latitude`/`longitude` at all. That README section describes a
  future/aspirational design, not what's built.
