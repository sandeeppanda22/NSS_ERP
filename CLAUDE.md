# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

> This file is a concise reference, not a running log — don't append session-by-session
> narrative to it. If a decision needs to be recorded permanently, it belongs in
> `docs/00_Project_Governance/GDR/` (once ratified) or in the relevant module's own SOLUTION
> doc.

## Setup

```
pip install -r requirements.txt
```
`requirements.txt` is UTF-16LE with CRLF line endings (Windows-migration artifact) — if a tool
errors reading it, re-save as UTF-8 rather than assuming it's corrupt.

Create `backend/.env` with `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — read with
no defaults at `backend/config/settings.py`, so the app won't start without them.

## Database

Hand-written PostgreSQL DDL under `database/ddl/`, numeric folder order, executed via `psql`
(no migration tool for this track — see `database/README.md` for the exact commands and full
phase-by-phase execution table):

1. `00_bootstrap/*` — 3 RBAC tables (`role_master`, `permission_master`, `role_permission`),
   created before Foundation since they have no FK dependencies — **DDL written, not yet
   committed**; seed data partial (`role_master`: 8 roles seeded; `permission_master`/
   `role_permission`: empty, blocked on the permission catalogue being frozen)
2. `01_foundation/01_extensions.sql` — `pgcrypto`, `pg_trgm`, `btree_gin`
3. `01_foundation/*` — 12 tables (master data, sequences, geography) — **implemented, seeded**
4. `02_organization/*` — 3 tables (`organization_type_master`, `organization_status_master`,
   `organization`) — **implemented, seeded**
5. `03_person/*` — superseded prototype, will be rewritten; don't build on it
6. `database/seed/` mirrors the same folder order

`./validate_foundation.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]` runs Foundation's DDL+seed
end-to-end against a running Postgres instance and checks row counts (Foundation only — doesn't
touch Organization/Person).

## Running the Django app

```
cd backend/
python manage.py migrate
python manage.py createsuperuser   # for /admin/
python manage.py runserver
```
`/` → redirects to `/login/` → on success, `/dashboard/`.

## Tests & lint

`python manage.py test` from `backend/` — every app's `tests.py` is currently the default empty
stub; there are no real tests yet. Run a single test the standard Django way:
`python manage.py test <app>.tests.<TestClass>.<test_method>`.

No lint/format tooling is configured (no flake8/black/ruff, no pre-commit). Don't add one
unilaterally — raise it as an open question if it's blocking.

## Architecture

**The one fact that isn't obvious from any single file:** there are two parallel,
*unreconciled* representations of core entities, and this will bite you if you assume a change
to one is reflected in the other.

- **Django ORM** (`backend/{authentication,foundation,membership,family,heritage}/models.py`) is
  what the running app actually uses — auto-increment PKs, plain `gender` CharField, etc.
- **Hand-written SQL DDL** (`database/ddl/`) — UUID `_pk` columns, `_code` business identifiers,
  FK-based master data — is the "real" intended schema per the SOLUTION docs
  (`docs/03_Solution/modules/`), but as of this writing is not read from or written to by any
  Django code. `01_foundation/` and `02_organization/` are implemented and seeded;
  `00_bootstrap/` (RBAC tables) has DDL written but is uncommitted with partial seed data;
  nothing else exists yet.

**Django app structure:** apps live directly under `backend/` (no `apps/` subdirectory):
`backend/{authentication, foundation, membership, family, heritage, dashboard, governance,
attendance, config}`. `authentication`, `foundation`, `membership`, `family`, and `heritage`
have real models; `dashboard`/`governance`/`attendance` are stubs. `INSTALLED_APPS`
(`backend/config/settings.py`) lists only `heritage`, `foundation`, `membership`, `family`,
`authentication` — `dashboard` is wired into `config/urls.py` without being in
`INSTALLED_APPS`. `family`/`membership`/`heritage` have models but no `urls.py` (admin-only).
Everything else described in the SOLUTION docs (`mahila`, `kumari`, `kishor`, `sevak`,
`publications`, `upbs`, `reports`, `administration`, etc.) has **no `backend/` app at all** —
design-only. Check `docs/PROJECT_DOCUMENTATION.md` before assuming otherwise.

**Cross-app model dependency:** `foundation.Person`/`foundation.Organization` are the hub models
every other real app hangs off — `membership.SanghaSevi` and `family.FamilyMembership` both FK
directly to `foundation.Person`; `membership` also FKs to `foundation.Organization`.
`authentication` (FKs only to Django's `auth.User`) and `heritage.Founder` (a standalone
singleton) are the exceptions. Altering `foundation.Person` has ripple effects across
`membership`/`family` but never `authentication`/`heritage`.

**DB naming (SQL DDL track):** tables `snake_case`; internal PK suffix `_pk`; FKs reference
internal PKs, never business IDs; business/external identifiers use `_code` — **never `_id`**
(some newer SOLUTION-layer docs under `docs/03_Solution/modules/` use `_id` in examples; that
contradicts the implemented DDL and is a known, tracked inconsistency — trust the DDL, not every
doc example). Audit columns: `created_at/created_by_sangha_sevi_pk`,
`updated_at/updated_by_sangha_sevi_pk`, `deleted_at/deleted_by_sangha_sevi_pk`, `is_active`
(soft delete — history is never hard-deleted).

**Governance Baseline is frozen** (`docs/00_Project_Governance/{AUTH,GOV,GDR,STD}/`) — AUTH vs
GOV separation, REF architecture, governance lifecycle, stable identifier model, GDR model, NSS
apex authority, parent-child org model, REF source-preservation rule are settled and not an
active design discussion. `docs/01_Authoritative_References/` holds source-faithful transcripts
of the NSS Bye-Law and Mahila Sangha Bye-Law (`REF-*`/`REF-MS-*`) — never paraphrase or
"correct" these, editorial notes only if explicitly marked as such.

**Frozen project-wide principles** (don't redesign around these without an explicit governance
decision): Person ≠ Member · Family First Model · History Never Deleted · Master Data Driven ·
By-Law Supremacy · Documentation First · Configuration Over Hardcoding · Permanent Business
Identifiers · Soft Delete + Audit Trail · Unified Body Governance Model · One Person = One
Membership = One Sangha Sevi ID.

**Documentation layout:**
```
docs/
├── PROJECT_DOCUMENTATION.md        ← deep, code-verified reference; read before proposing
│                                      schema/module-layout changes
├── 00_Project_Governance/{AUTH, GOV, GDR, STD}/
├── 01_Authoritative_References/NSS/ , MAHILA_SANGHA/   (source-faithful REF corpus)
├── 02_Requirements/                 (scaffolded, empty)
├── 03_Solution/modules/<module>/     (per-module design docs — overview/ERD/business-rules/
│                                      table-design; NOT the same thing as a same-named
│                                      backend/ Django app — check before assuming overlap)
├── 04_Testing/                      (scaffolded, empty)
└── 05_Releases/
```

**Git branch policy:** `feature/<work>` → complete & verify → commit → merge into `develop` →
only then create the next feature branch. `main` advances only via a documented tag+release
process, never ad-hoc branch sync. Confirm the current branch before making changes — don't
assume a rename/move succeeded without verifying via `git status`/`git ls-files`.

**Two git remotes:** `personal` (`github.com/sandeeppanda22/NSS_ERP`, daily dev) → PR →
`org` (`github.com/NilachalaSaraswataSangha/NSS_ERP`, deploy source). `git fetch`/`push` to
either is commonly blocked in-sandbox by a domain-allowlist restriction — push manually from a
terminal if a sandboxed session can't.

**Approved tech-stack direction** (`docs/03_Solution/architecture/TECH_STACK_DECISIONS.md`) —
Django 6 (Templates + Tailwind/DaisyUI/HTMX/Alpine, replacing Bootstrap 5) + FastAPI/Uvicorn API
layer + Flutter mobile — is **not yet reflected in `backend/`**, which still runs Bootstrap 5
with no FastAPI wiring. Don't assume code has caught up to that decision record.
