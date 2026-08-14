# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

> **Also serves as:** shared memory between the AI assistants working on this repository —
> **Claude** (in VS Code) and **Enchanté**. Both read this file at session start and append to
> it after any meaningful decision or context shift. This is an **operational aid**, not a
> governance artifact — it does not replace or override `docs/00_Project_Governance/GDR-001` or
> any approved governance document. Formal governance decisions belong in the Governance
> Decision Register once ratified. Where this file and live repo state disagree, **live repo
> state wins** — always verify with `git status` / `git log` / `git branch --show-current`
> before acting on anything written here (this is itself a project rule — see §11).

---

## 0. Commands & Architecture Quick Reference

**Setup (from repo root):**
```
pip install -r requirements.txt
```
Create `backend/.env` with `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — read with
no defaults at `backend/config/settings.py`, so the app won't start without them.

**Database:** provision PostgreSQL with the `pgcrypto` extension, then run the hand-written DDL
under `database/ddl/` in numeric folder order (`01_foundation` → `02_organization` [currently
all 0-byte placeholders, nothing to run] → `03_person`), then `database/seed/` in the same
order. This raw-SQL track is **not** consumed by the Django app below — see the architecture
note.

**Run the Django app (from `backend/`):**
```
python manage.py migrate
python manage.py createsuperuser   # for /admin/
python manage.py runserver
```
Visit `/` → redirects to `/login/` → on success, `/dashboard/`.

**Tests:** `python manage.py test` — but every app's `tests.py` is currently the default empty
stub; there are no real tests in the repo yet. When adding one, run a single test the standard
Django way: `python manage.py test <app>.tests.<TestClass>.<test_method>`.

**Lint/format:** none configured (no flake8/black/ruff config, no pre-commit). Don't invent one
unilaterally — raise it as an open question if it's blocking.

**The one architectural fact that isn't obvious from any single file:** there are two parallel,
*unreconciled* representations of core entities. Django ORM models (`foundation.Person`,
`foundation.Organization`, auto-increment PKs, e.g. a plain `gender` CharField) are what the
running app actually uses; the hand-written SQL DDL under `database/ddl/` (UUID `_pk` columns,
`person_code`/business-`_code` identifiers, `gender_pk` FK to `gender_master`) is the "real"
intended schema per the standards docs but is not read from or written to by any Django code.
Don't assume a change to one is reflected in the other. Full detail, plus the current
directory-by-directory breakdown of `backend/`, `database/`, and `docs/`, lives in
`docs/PROJECT_DOCUMENTATION.md` — read that before proposing schema or module-layout changes,
rather than rediscovering structure from scratch.

---

## 1. Project Identity

- **Project:** NSS ERP — Nilachala Saraswata Sangha Enterprise Resource Planning System
- **Organization:** Nilachala Saraswata Sangha (NSS)
- **Current repo location:** `/Users/sandeep.panda03/Documents/NSS_ERP` (macOS)
  - **Migrated from:** `D:\Important\NSS\NSS_ERP` (Windows + VS Code + PowerShell). User has
    fully moved to Mac; the Windows path is historical only — do not reference it as current.
- **Not a generic corporate ERP.** Must reflect NSS's actual constitutional, spiritual,
  organizational and family structure. UI philosophy: traditional, simple, mobile-friendly,
  accessible to elder members, low training requirement. Avoid SAP-style/corporate-dashboard
  complexity, deep nested menus, technical jargon.
- **Foundational philosophy:**
  `Constitution First → Governance → Requirements → Solution → Implementation`
  and for delivery: `Database First → API First → UI First`, both now subordinate to the
  frozen Governance Baseline v1.0 (§2).

## 2. Governance Baseline v1.0 — FROZEN

Governance architecture is **not an active design discussion**. Future work fits into the
existing framework; it does not redesign it. Do not reopen: AUTH vs GOV separation, REF
architecture, governance lifecycle, stable identifier model, GDR model, NSS apex authority,
parent-child org model, REF source-preservation rule, repository folder philosophy, SOLUTION
terminology, or the baseline itself.

**Lifecycle:**
```
Official Constitution & Bye-Laws → REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE
```
**GDR is cross-cutting, not a lifecycle layer** — it sits alongside the chain as the
governance-decision/approval/record mechanism, not between GOV and REQ. This was a specific
correction identified during the six-phase governance doc review (§6); AUTH-001's hierarchy
diagram must NOT be changed to insert GDR — that correction belongs in GOV-001.

**Layer responsibilities:** REF = authoritative source (source-faithful, no interpretation) ·
AUTH = manages/standardizes authoritative references · GOV = governance interpretation ·
REQ = business/functional requirements · SOLUTION = DB/API/UI/security/integration/deployment
design · CODE = implementation · TEST = validation · RELEASE = versioned publication ·
GDR = authoritative decision history (cross-cutting).

**Frozen org/governance principles (permanent IDs, never renumbered):**
`GOV-ORG-001..005` (NSS apex authority; constitutional precedence; single-hierarchy integrity;
only officially-approved docs enter REF; constitutional traceability required or explicitly
flagged as an ERP implementation decision) · `GOV-DATA-001` (parent-child integrity) ·
`GOV-LIFE-001` (governance change control — no informal edits to frozen standards) ·
`GOV-LIFE-002` (immutable rule identifiers; deprecated rules keep their ID and point to
successors).

## 3. Live-Verified Repository State (as of 2026-08-12, updated same day — after committing,
pushing, and fast-forward-merging `feature/ref-documentation` into `develop`)

> Verified via `git status` / `git log` / `git branch` — do not trust handoff-doc claims over
> this without re-verifying, since handoffs go stale.

- **Branch (updated 2026-08-14, later same day):** `feature/ref-renaming` has since been merged/
  fast-forwarded into `develop` — both now identical at `c27af10 "docs: fix leftover rename
  references and drift found in /document-project + /init pass"`, and both in sync with their
  `pie/` remotes. Active branch is `develop`. Working tree clean, nothing uncommitted. The
  `feature/ref-renaming`-at-`4b81c31` state described just below, and the `develop`/`a2e6a6a`
  state in the two bullets after that, are both historical snapshots superseded by this one —
  kept for the commit narrative, not current branch/HEAD state.
- **Latest 2 commits (both now on `develop`):** `a2e6a6a "docs(ref): add Mahila Sangha REF-MS
  corpus, refresh docs to match"` → `a9cd4bc "docs(ref): complete REF corpus source-verification
  pass, add BY-LAW originals"`.
- **Prior working-tree state (now resolved, committed as `a2e6a6a`):** small "Repository Path"
  metadata corrections in `REF-001`, `REF-002`, `REF-003-C`, `REF-003-C(i)(1)`, and an update to
  `docs/01_Authoritative_References/MAHILA_SANGHA/README.md` (from "reserved, nothing added" to
  documenting the now-complete 22-document `REF-MS-XXX` corpus), plus the 12
  `MAHILA_SANGHA/SECTION-*` folders themselves (each holding its `REF-MS-*` document — see
  bullet below).
- **Recent commits (newest first):** `a2e6a6a` → `a9cd4bc` (both above) → AUTH-001 minor
  corrections → GDR-001 added → GOV-005 added → GOV-004 added → GOV-003 added → GOV-002 added
  → GOV-001 added → AUTH-001 added (replacing an older AUTH-001) → merge of
  `feature/ref-documentation` into `develop` → authoritative reference repository standard
  added.
- **Mahila Sangha REF corpus — new, complete as of this pass:**
  `docs/01_Authoritative_References/MAHILA_SANGHA/` is a **sibling** folder to `.../NSS/` (not
  nested under it) and now holds 22 documents across Sections A–M
  (`SECTION-A_MEMORANDUM_AND_REGISTRATION` … `SECTION-M_DISSOLUTION`), transcribed from
  `BY-LAW/NSS - Mahila Sangha/NSS Mahila Sangha By-Law.pdf` (docx-cross-checked). Uses its own
  `REF-MS-XXX` identifier family, distinct from NSS's `REF-00X` family — see
  `docs/PROJECT_DOCUMENTATION.md` → `docs/01_Authoritative_References/MAHILA_SANGHA/` detail for
  the full section/document map. **Known gap surfaced during this pass:** several `REF-MS-*`
  documents cite `AUTH-001` as defining the `REF-MS` family, but `AUTH-001`'s current text has
  no such definition yet — flagged in `docs/PROJECT_DOCUMENTATION.md` Open questions, not fixed
  here (AUTH-001 edits follow the controlled process in §6).
- **AUTH-001 status:** further along than some handoff notes suggest — already has a
  correction commit (`5ec61c0 "docs(auth): Some Minor Changes to AUTH-001 File"`). Verify
  actual current content before assuming it's still mid-correction.
- **REF corpus on disk — fully corrected and verified against both source PDF and docx (as of 2026-08-12):**
  - `REF-001` (Section A, NSS Constitution) — present, fully restructured to match confirmed
    source sequence: Name → Registered Office → "Special Features : PREAMBLE" (repositioned
    here, not at the top) → short "3. Objects of the Society" intro paragraph → Memorandum
    of Association ("6." — no heading text in source) with founding-members table (9 names +
    addresses, cross-referenced from REF-003-C(i)(1) where not printed directly), witnesses
    table, and full certification/registration chain → second "3. OBJECTS OF THE SOCIETY:"
    heading with "Bye-law Of Nilachala Saraswata Sangha" sub-heading + full numbered list
    (1-20). Confirmed: no heading numbered 4 or 5 exists in the source (3 jumps to 6).
  - `REF-002` (Section B, Membership Bye-Laws) — present, correct (a)-(d) lettering with
    (i)-(v) sub-items matching source exactly.
  - `REF-003-C` … `REF-003-I` — present, spanning **Section C through Section I only**.
    **There is no "Section J" in the source** — this was a confirmed error in earlier
    project assumptions (including an earlier version of this file) and has been corrected.
    The former `REF-003-017` (which combined two 1975 Resolutions under an invented
    "Section J") has been deleted from the repository. The two 1975 Resolutions are
    constitutional amendments to **Section C** and are now filed as separate documents
    adjacent to the clauses they amend: `REF-003-C(i)(2)-1975-01` (amends REF-003-C(i)(2),
    Functions of the Governing Body) and `REF-003-C(i)(8)-1975-02` (amends REF-003-C(i)(5) and
    REF-003-C(i)(8), Duties of the Secretary and Parichalak). Each carries the source's actual
    letterhead/attestation content (founding letterhead on Resolution No.1; 3-member
    Executive Body signature block on Resolution No.2).
  - Funds of the Kendra Sangha (Section F) is split into **three** documents per explicit
    instruction, mirroring the source's F[A]/[b]/[c] structure: `REF-003-F[A]` (Funds, i-ix),
    `REF-003-F[b]` (Maintenance, single statement), `REF-003-F[c]_Utilisation_of_the_Funds`
    (Utilisation, i-vi) — the third file is new, not a rename of an existing one.
  - Dissolution (`REF-003-I`, Section I) now includes its own certification/signature
    block (President/Secretary-Parichalak/Vice-President + registration table + Registrar
    countersignature), distinct from the Memorandum's certification and the Resolutions'
    Executive Body attestation — three separate certification instances in the source,
    preserved separately, not merged.
  - All clause-level numbering across Sections A-I now matches the source's actual markers
    (numerals, letters, roman numerals) exactly — replacing an earlier pass that had used
    generic sequential "Clause N" labels throughout. One confirmed correction along the way:
    Advisory Board's cross-reference to the Governing Body's budget clause is **(xiii)**,
    not (xii) — the PDF's OCR misread (xii); the clean-text docx (xiii) was confirmed correct.
  - Repository is organized by section folder (`SECTION-A_...` … `SECTION-I_...`), each
    containing its REF file(s) — folders are navigation only, identity lives in the filename.
- **Governance docs present (updated 2026-08-14):** `AUTH-001`, `GOV-001..005`,
  `GDR-001..004` — all exist under `docs/00_Project_Governance/{AUTH,GOV,GDR}/`.
- **Module docs present:** `docs/03_Solution/modules/organization/` and
  `docs/03_Solution/modules/person/`, each with `01_design`, `02_erd`, `03_business_rules`,
  `04_table_design` (+ person has a `README.md`).
- **Standards docs present:** `docs/00_Project_Governance/STD/01_project_standards.md` …
  `05_security_standards.md`.
- **Releases present:** `v0.1.0` through `v0.5.1` under `docs/05_Releases/`.
- **Other branches that exist but are NOT current:** `develop`, `main`,
  `feature/admin-setup`, `feature/founder-heritage`, `feature/membership-design`,
  `feature/person-ddl`, `feature/person-management`, `feature/ref-documentation`. Notably
  `feature/organization-module` (referenced in an older handoff phase) does **not** appear in
  the branch list — that handoff phase was stale; trust the live branch list over it.

## 4. Git Branch Policy (standing rule)

```
feature/<work> → complete & verify → commit → merge into develop → THEN create next feature branch
```
Never create the next feature branch while the current one is unfinished. Always state/confirm
the current branch before making changes. **Do not assume a rename/move succeeded** just because
the command was issued — verify with `git status` / `git ls-files` (this bit the project once
with a GOV-005 rename that silently failed because the old path wasn't tracked as expected).

**Organization Module is frozen — the current renaming/governance work is explicitly NOT an
invitation to reopen it.**

## 5. Documentation Architecture

```
docs/
├── PROJECT_DOCUMENTATION.md
├── 00_Project_Governance/{AUTH, GOV, GDR, STD}/
├── 01_Authoritative_References/NSS/SECTION-A..I/ (+ MAHILA_SANGHA/SECTION-A..M/ complete;
│   RESOLUTIONS/, CIRCULARS/, NOTIFICATIONS/ still planned)
├── 02_Requirements/ (scaffolded, empty)
├── 03_Solution/modules/{organization, person, ...}/ (+ api/architecture/database/infrastructure/security/ui scaffolding)
├── 04_Testing/ (scaffolded, empty)
└── 05_Releases/
```
`modules/` and `standards/` used to live directly under `docs/` — as of the 2026-08-12
folder-consolidation pass (see Session Log) they were moved to `docs/03_Solution/modules/` and
`docs/00_Project_Governance/STD/` respectively. If you see either old path referenced anywhere,
it's stale.
REF documents preserve **original authoritative wording** — no paraphrasing, no ERP
interpretation injected into REF, no silently "correcting" the source, no merging unrelated
provisions, no inventing missing clauses. Editorial notes allowed only if clearly marked as
editorial metadata. REF identifiers belong to the *document*, not the folder — e.g.
`REF-003-C(2)(xiii)`, not a filesystem path.

## 6. Governance Doc Review — Six-Phase Review (COMPLETE) & Open Corrections

Phases completed: Structural → Formatting → Terminology → Cross-Reference → Governance Rule →
Governance Hierarchy. Formatting standard: `# Title` → `## Document Metadata / Revision
History / Table of Contents` → `## N. Section` → `### Rule/Subsection` → `#### rare` →
`## Appendix A/B/...` → ends with `# End of Document`. TOC uses flat numbered points, not deep
nesting. Capitalize first word of sections/subsections/headings; ordinary bullets use sentence
case.

**Corrections — all applied and verified live as of 2026-08-13** (previously tracked here as
pending; each now has a real fix commit and was spot-checked against current file content —
do not redo this work):
1. AUTH-001 — structural/TOC/formatting fixes applied (`a3198b3`, `5ec61c0`); substantive
   wording/rule IDs/examples preserved.
2. GOV-001 — GDR hierarchy fixed to cross-cutting, not a lifecycle layer (`46b5c5c`); confirmed
   in GOV-ORG-002, Appendix A, and Appendix B text.
3. GOV-002 — orphan `GOV-DATA-005` removed from Appendix B (`bfba73c`); confirmed absent from
   current file.
4. GOV-003 — front-matter formatting fixed (`e0d554a`).
5. GOV-004 — front-matter fixed, stray mid-document `End of Document` removed (`c40a3c9`).
6. GOV-005 — terminology standardized on **"Impact Assessment"** (`11517a5`); confirmed no
   "Impact Analysis" remains in current file.
7. GDR-001 — standardized on **"Decision Identifier"** in normative prose, "Decision ID" kept
   only as a table column label (`4e13b8b`); confirmed `GDR-DEC-004` (decision-level) vs
   `GDR-DATA-005` (register-level) are explicitly distinguished, not duplicated, in current file.

**Open governance decisions:** none remaining as of 2026-08-14 — see the three resolved entries
below. If a new one surfaces, add it here and do not invent an answer to it without an
explicit human decision.

**Resolved (2026-08-14, see §12 and GDR-004):** Governance Authority / Decision Authority /
Approving Authority / Approver / Project Owner / Project Steering Committee relationship.
`Project Owner` = Nilachala Saraswata Sangha (NSS) itself. `Governance Authority` (`GOV-ROLE-002`)
= `Project Steering Committee` — same body, not two; this is the body recorded as `Owner` and
`Approver` in AUTH/GOV/GDR document metadata. Final decision authority for governance decisions
recorded in the GDR rests with the `NSS Governing Body` (constitutional body, REF-003-C(i)(1)),
exercised through its President (REF-003-C(i)(3)) and/or Parichalak (REF-003-C(i)(8)) — not the
Governance Authority/Project Steering Committee — per new rule `GOV-ROLE-006` in `GOV-001`.
`Approving Authority` was retired as a phantom term (never used anywhere in the corpus, same
pattern as the `"Non-Conformity"` resolution below). The already-approved `GDR-002`/`GDR-003`
had their `Decision Authority` field corrected from `NSS ERP Governance Committee` to
`NSS Governing Body` via a preserved Correction Note (not a silent rewrite); `GOV-002..005` and
`GDR-001` had their `Owner` field corrected from `NSS ERP Governance Committee` to
`Project Steering Committee` to match.

**Resolved (2026-08-13, no document changes needed):** Governance/Non-Compliance vs
"Non-Conformity" terminology. Checked every governance doc (`AUTH-001`, `GOV-001..005`,
`GDR-001`) — `Compliance`/`Non-Compliance` is already used consistently everywhere (same
hyphenation and capitalization convention throughout, including rule IDs `GOV-COMP-001..005`);
`"Non-Conformity"` was never introduced anywhere in the corpus — it only existed as the
term-to-avoid in this file's own description of the question. Nothing to fix; closing the
question as already settled in practice.

**Resolved (2026-08-13, see §12 and GDR-003):** Governance document status lifecycle. Adopted
`Draft → Review → Approved → Superseded/Retired` as `GOV-LIFE-006` in `GOV-001` — deliberately
4 states, no document-level `Frozen` (that term already means the Governance Baseline as a
whole and, separately, per-rule maturity). The per-rule field that used to share the name
`Status` was renamed to `Rule Maturity` (44 occurrences in `AUTH-001`, 20 in `GOV-001`) to
eliminate the contradiction of a `Draft` document containing `Frozen` rules. `AUTH-001` and
`GOV-001` were both advanced from Status `Draft` to `Approved` (now v1.1.0) to match how they
are actually used project-wide.

**Working rule for every governance-doc edit (still applies to any *future* correction):**
retrieve actual current source → preserve substantive content → apply only approved structural
corrections → deliver the *complete* replacement file → user swaps it in → `git diff --check` +
`git diff` review → commit only after verification → move to next document. The
AUTH-001 → GOV-001 → GOV-002 → GOV-003 → GOV-004 → GOV-005 → GDR-001 sequence itself is now
fully done (see corrections list above) — this rule remains for whatever governance edit comes
next, not a resumption of that sequence.

**Terminology note:** In this project, **"AUTH-001" always means the Authoritative Reference
Standard governance document** — never "Authentication UI-001." An earlier session conflated
these; don't repeat that.

## 7. Frozen Architecture Principles (project-wide)

```
Person ≠ Member          Family First Model          History Never Deleted
Master Data Driven        By-Law Supremacy            Documentation First
Configuration Over Hardcoding                          Auditability
Permanent Business Identifiers                         Soft Delete + Audit Trail
Unified Body Governance Model
One Person = One Membership = One Sangha Sevi ID
```

**Person module (frozen):** Person Code = permanent, system-generated, unique, never reused.
Contact rule: `mobile_number` UNIQUE+nullable, `email` NOT UNIQUE+nullable, but
`mobile_number IS NOT NULL OR email IS NOT NULL` must always hold — enforce via DB CHECK
constraint. DOB optional for Person, mandatory before Membership approval. Multiple addresses
supported. Soft delete + audit enabled. Photo/doc storage deferred to Document Management.

**Membership (frozen):** `Sangha Sevi ID` format `SS00000001` — system generated, unique,
permanent, never reused. Categories: Probationary / Regular / Associate. Renewal deadline tied
to Dola Purnima, **no grace period**. Full rule set lives in `04_MEMBERSHIP_BUSINESS_RULES.md`
(if not yet in repo, treat as pending creation) — REQ/SOLUTION work must not contradict it.

**Organization:** Root = NSS; no independent organizational roots for subordinate bodies.
`ANCHALIKA` and `ZILLA` = administrative units; `SAKHA` = physical Sangha location, existing
under `ANCHALIKA` or `ZILLA`; `PATHA_CHAKRA` = an organization type sitting directly under
`KENDRA` (not under `ANCHALIKA`/`ZILLA`), may operate within India or internationally (root
`README.md` § Organization Hierarchy). Prior design leaned toward one organization → one
address (on the `organization` table directly, not a separate `organization_address` table) —
**do not reopen without checking current governance baseline first; Organization Module is
frozen.**

**Mahila Sangha:** Every Sakha Sangha (branch) has its own local Mahila Sangha (women's wing),
per `REF-001` Clause 12 ("To organise 'Mahila Sanghas' in different 'Sakha Sanghas'... which
will function as a part of the concerned Sakha Sangha and the Kendra Sangha"). All of these
local Mahila Sanghas are governed centrally by **one Mahila Parichalana Mandali**. The 22
`REF-MS-*` documents transcribed from `NSS_Mahila_Sangha_Bye_Law.docx` are the **central
Mandali's own Bye-Law** — its `REF-MS-6(i)` through `REF-MS-6(viii)` clauses (President,
Vice-President, Secretary, Joint Secretary, Treasurer, Parichalak) define the Mandali's own
governing structure, not a single local branch's. **No separate membership system** — Mahila
members use the same Probationary/Regular/Associate framework as everyone else. Confirmed
2026-08-14 by project owner; see §12.

**Kumari Sangha / Kishore Puja:** Each has its own ID distinct from Sangha Sevi ID
(`Kumari ID ≠ Sangha Sevi ID`, `Kishore ID ≠ Sangha Sevi ID`) — not treated as ordinary
membership.

**Sevak Sangha:** Partially frozen only — foundation exists but executive structure,
membership lifecycle, training hierarchy, governance model, and operational structure are
still incomplete.

**Attendance:** Secretary = primary operational authority; President = oversight/appeal
authority. Attendance Enforcement + Attendance Review are frozen.

## 8. Technical Architecture

| Area | Choice |
|---|---|
| Backend web/admin | Django (Templates + Bootstrap 5 + HTMX), Django ORM |
| API layer | FastAPI |
| Database | PostgreSQL |
| Frontend philosophy | Traditional/simple, NOT corporate/SAP-style |
| Dev environment | VS Code, DBeaver, Git/GitHub |
| Security | UUID internal PKs, separate business IDs, RBAC, RLS, immutable audit, soft delete |
| Deployment (earlier direction) | Ubuntu, Docker, Nginx, PostgreSQL |

**Django app structure — corrected against actual code (2026-08-12, updated same day —
`heritage` merged into `develop`):** apps live directly under `backend/` (no `apps/`
subdirectory): `backend/{authentication, foundation, family, membership, heritage, dashboard,
governance, attendance, config}`. Of these, `authentication`, `foundation`, `membership`,
`family`, and `heritage` (singleton `Founder` model) have real models; `dashboard`/
`governance`/`attendance` are stubs (empty `models.py`, no `urls.py` for governance/attendance).
Only `authentication`, `dashboard`, and `foundation` are wired into `config/urls.py`; `family`,
`membership`, `heritage` have models but no `urls.py` — admin-only. `mahila`, `kumari`,
`kishore`, `sevak`, `publications`, `upbs`, `reports`, `administration` are **not yet scaffolded
at all** — planned only. Full detail: `docs/PROJECT_DOCUMENTATION.md` §Directory structure /
§Gotchas. Do not casually redesign this structure.

**Cross-app model dependency (not obvious without reading multiple `models.py` files):**
`foundation.Person`/`foundation.Organization` are the hub models every other app's real
models hang off — `membership.SanghaSevi` and `family.FamilyMembership` both FK directly to
`foundation.Person` (`backend/membership/models.py`, `backend/family/models.py`); `membership`
also FKs to `foundation.Organization`. `authentication` and `heritage` are the exceptions —
`authentication` FKs only to Django's built-in `auth.User`, and `heritage.Founder` is a
standalone singleton with no FK to `foundation` at all. Migrating or altering `foundation.Person`
therefore has ripple effects across `membership` and `family`, but never `authentication` or
`heritage`.

**DB naming standards:** tables `snake_case` (e.g. `family_group`); internal PK suffix
`_pk` (e.g. `person_pk`); FKs reference internal PKs, never business IDs; audit columns:
`created_at/created_by_sangha_sevi_pk, updated_at/updated_by_sangha_sevi_pk,
deleted_at/deleted_by_sangha_sevi_pk, is_active`.
**Correction (2026-08-12):** the actual SQL DDL uses `_code` (not `_id`) for business
identifiers — `person_code`, `country_code`, `sequence_code`, etc. — never `_id`. The prior
`sangha_sevi_id` example was a Django model field name (`backend/membership/models.py`), not a
SQL/DDL convention; don't generalize from it. Follow `_code` for new DDL.

**Schema scale:** conceptual table count has been estimated anywhere from ~88 to ~95+ to a
projected 110–130 depending on remaining operational modules — **these are estimates, not a
frozen final count.** Do not treat any single number as authoritative; do not convert
unresolved conceptual tables into production schema before REQ/SOLUTION for that area is
settled.

## 9. UI Roadmap (Sprint 1 — established baseline)

```
UI-001 Login          UI-002 Kendra Dashboard      UI-003 Sakha Dashboard
UI-004 Member Search  UI-005 Member Profile        UI-006 Family Dashboard (frozen)
```
Top-level nav: Dashboard, Membership, Family, Governance, Attendance, Mahila Sangha, Kumari
Sangha, Kishore Puja, Sevak Sangha, Founder & Heritage, Publications, UPBS, Reports,
Administration.

## 10. Frozen Domains (do not redesign) vs Still-Open Domains

**Frozen/substantially frozen:** Founder & Heritage, Governance Framework (Unified Body
Governance Model, Advisory Board, General Body, Election Framework, Vacancy Framework),
Membership Types/Identity/Renewal/Transfer, Probationary→Regular progression, Parichaya Patra
foundation, Attendance Enforcement/Review, Family foundation, Mahila Sangha + Mandali, Kumari
Sangha, Kishore Puja, UPBS registration foundation, technical architecture foundation, master
data foundation, project standards, decision hierarchy, Organization Module, Person module.

**Partially frozen:** Sevak Sangha.

**Still open / need REQ-level work:** Membership Reinstatement, Disciplinary Workflow, Patha
Chakra, Gruhasana, Sangha Puja, Mahila Puja, Pali System, Seva-Puja, Sevak Sangha operational
structure, UPBS Volunteer structure + Day 1/2/3 operations, detailed Finance workflows.

## 11. Standing Working Rules

- **File creation convention:** for new folders/files, give the shell/PowerShell creation
  command first, *then* the file contents — don't bundle file contents into a heredoc/write
  command unless explicitly asked.
- **Always refer to existing project source/module docs before proposing schema, business-rule,
  or architecture changes** — don't replace a frozen decision with generic "ERP best practice."
- **Complete-file rule:** any requested document/file must be delivered as the complete file,
  never partial, never with `...` / "rest unchanged" placeholders.
- **Verify before declaring done:** git renames, merges, and file moves must be confirmed via
  `git status`/`git log`/`git ls-files` — never assume success from the command alone.

## 12. Session Log

<!-- Newest entries at the top. -->

### 2026-08-14 — Clarified Mahila Parichalana Mandali structure: central body governing all Sakha Sangha-level Mahila Sanghas (Enchanté)
- Context: An earlier §13 open question stated the Mandali's composition/election/term needed
  source verification. Exhaustive search of both Bye-Law PDFs/docx files found zero mentions of
  "Mahila Parichalana Mandali" anywhere in the source text, prompting a check-in with the
  project owner rather than guessing. Owner corrected an intermediate (also wrong) framing in
  two steps: (1) confirmed `REF-001` Clause 12 already establishes that every Sakha Sangha has
  its own local Mahila Sangha, functioning as part of that Sakha Sangha and the Kendra Sangha;
  (2) confirmed all of these local Mahila Sanghas are governed centrally by **one** Mahila
  Parichalana Mandali, and that the 22 `REF-MS-*` documents (transcribed from
  `NSS_Mahila_Sangha_Bye_Law.docx`) are that **central Mandali's own Bye-Law** — its
  `REF-MS-6(i)`–`REF-MS-6(viii)` clauses define the Mandali's own governing structure, not one
  local branch's.
- Decision/Outcome: Corrected §7 and §13 of this file, and
  `docs/03_Solution/modules/mahila/README.md`, to state the Mandali is a single central
  Governing Body spanning all Sakha Sangha-level Mahila Sanghas — not a separate unverified
  layer, and not scoped to one local branch. §13's open item is now resolved and struck through.
- Follow-up: None outstanding on this specific question. The only remaining genuinely open item
  in §13 is the final conceptual schema table count.

### 2026-08-14 — Renamed Sections C-I to composite clause locators; corrected AUTH-001's fictional examples (Enchanté)
- Context: User asked to rename "the bylaw files." Investigation on `feature/ref-renaming`
  found the NSS `REF-003-001`..`REF-003-016` files used flat sequential numbering, while two
  1975 resolution files and `REF-003-F[c]_Utilisation_of_the_Funds.md` already used a
  composite-locator convention (`REF-003-C(i)(2)-1975-01`, etc.) matching true source lettering
  pulled directly from `NSS_Bye_Law.docx` (Section C → `(i)` Governing Body → `(1)`–`(8)`;
  `(ii)` Advisory Board = actual Section D; `(iii)` General Body = actual Section E). Also found
  `AUTH-001` itself contradicted this precedent: its own `AUTH-ID-002`/`003`/`004` examples and
  Appendix B/C described a fictional one-REF-family-per-section scheme (`REF-004`→D ...
  `REF-010`→J) that was never implemented anywhere in the repo. User confirmed scope (option 3:
  rename the REF documentation files, not the source `BY-LAW/*` originals) and approved fixing
  `AUTH-001` in the same pass.
- Decision/Outcome: Renamed 16 files via `git mv` (detected as renames):
  `REF-003-001`→`REF-003-C`, `002`→`C(i)(1)`, `003`→`C(i)(2)`, `004`→`C(i)(3)`, `005`→`C(i)(4)`,
  `006`→`C(i)(5)`, `007`→`C(i)(6)`, `008`→`C(i)(7)`, `009`→`C(i)(8)`, `010`→`D`, `011`→`E`,
  `012`→`F[A]`, `013`→`F[b]`, `014`→`G`, `015`→`H`, `016`→`I`. Propagated the rename across 355
  cross-references in 44 files (internal `Document ID` metadata, this file, `GOV-001`,
  `GDR-004`, all 22 `REF-MS-*` docs, `PROJECT_DOCUMENTATION.md`, section READMEs). Corrected
  `AUTH-001`: `AUTH-ID-002` now states a REF family may span multiple contiguous sections (not
  strictly one per section); `AUTH-ID-003`/`004` examples and Appendix B/C replaced with the
  real mapping (`REF-003` spans Sections C–I) and real in-repo filenames. Committed as `4b81c31`
  on `feature/ref-renaming`; a follow-up drift-fix pass (`c27af10`, Claude Code) caught leftover
  references. Both pushed, merged into `develop` (clean fast-forward), pushed. `git diff --check`
  clean throughout; zero stale sequential-ID references remain anywhere in the repo.
- Follow-up: None from this change — it was a structural correction initiated this session, not
  a pre-existing open question, so it does not close any item in §13. The two genuinely open
  items in §13 (Mandali composition, final schema table count) remain untouched.

### 2026-08-14 — Resolved final open governance decision (authority-role relationships); added GDR-004 (Claude Code)
- Context: User asked to tackle the last open governance decision from §6: the relationship
  between Governance Authority, Decision Authority, Approving Authority, Approver, Project
  Owner, and Project Steering Committee. Investigation found `Project Owner` and `Governance
  Authority` are formally defined roles in `GOV-001` (`GOV-ROLE-001`/`002`) but never tied to a
  named body, while `Project Steering Committee` and `NSS ERP Governance Committee` are used
  as concrete values across `GOV-002..005`/`GDR-001` metadata (and `NSS ERP Governance
  Committee` as `Decision Authority` in the already-approved `GDR-002`/`GDR-003`) without ever
  being formally defined as roles. `Approving Authority` turned out to be a phantom term, never
  used anywhere in the corpus — same pattern as the `"Non-Conformity"` resolution. Presented
  this mapping via AskUserQuestion; the user rejected the initial multi-choice framing wanting
  to clarify in their own words first, then answered directly across two follow-up exchanges:
  "Project Owner is NSS. Project Steering Committee handles the project. NSS Governing Body is
  final decision authority," then, on the remaining ambiguity, "Project Steering Committee: —
  maintains the governance framework, reviews proposals, evaluates GDR entries, monitors
  compliance. All decision related things will be handled by NSS Governing Body/NSS
  President/NSS Parichalak."
- Decision/Outcome: Recorded as `GDR-004`. `GOV-001` gained: an explicit "Project Owner = NSS
  itself" clarification on `GOV-ROLE-001`; an explicit "Governance Authority = Project Steering
  Committee (same body)" clarification on `GOV-ROLE-002`; and a new rule `GOV-ROLE-006 — Final
  Decision Authority`, naming the `NSS Governing Body` (REF-003-C(i)(1), via President
  REF-003-C(i)(3)/Parichalak REF-003-C(i)(8)) as final authority over GDR decisions, distinct from the
  Governance Authority's day-to-day framework-maintenance role. Version 1.1.0 → 1.2.0. Corrected
  the `Owner` field in `GOV-002` through `GOV-005` and `GDR-001` from `NSS ERP Governance
  Committee` to `Project Steering Committee` (5 files). Corrected the `Decision Authority` field
  in the already-approved `GDR-002`/`GDR-003` from `NSS ERP Governance Committee` to `NSS
  Governing Body` — not a silent rewrite: added a "Correction Note" section to each preserving
  the original attribution per `GDR-DATA-003` (Complete Decision History), since both are
  `Approved` decision records. Updated `GDR/README.md` and `GOV/README.md`. Updated this file's
  §6/§13: **all three** governance decisions originally flagged as open in §6 are now resolved
  — none remain outstanding.
- Follow-up: none outstanding on governance terminology/structure. Remaining genuinely open
  items in the project are domain-specific (Mahila Parichalana Mandali composition; final
  schema table count) — see §13.

### 2026-08-13 — Closed Non-Compliance vs "Non-Conformity" terminology question; no document changes needed (Claude Code)
- Context: User asked to tackle the last remaining open governance decision from §6 (besides
  the authority-role-relationship question): whether to standardize on "Governance
  Compliance/Non-Compliance" or "Non-Conformity" terminology.
- Decision/Outcome: Searched every governance document (`AUTH-001`, `GOV-001` through
  `GOV-005`, `GDR-001`) for both terms before proposing anything. Found `Compliance`/
  `Non-Compliance` already used consistently everywhere — same hyphenation and capitalization
  convention throughout, including the `GOV-COMP-001` through `GOV-COMP-005` rule IDs in
  `GOV-001` and dedicated "Non-Compliance Management" sections in `GOV-004`, `GOV-005`, and
  `GDR-001`. `"Non-Conformity"` was never introduced anywhere in the actual corpus — it only
  ever existed as the term-to-avoid inside this file's own description of the open question.
  Asked the user how to close a question that requires no document edits (quiet CLAUDE.md
  closure vs. a formal GDR-004 record anyway); user chose the quiet closure. Updated §6/§13
  accordingly — no AUTH/GOV/GDR document was touched.
- Follow-up: none outstanding on this item. The one remaining "Open governance decision" in §6
  is the Governance Authority / Decision Authority / Approving Authority / Project Owner /
  Project Steering Committee relationship question — still needs an explicit human decision.

### 2026-08-13 — Resolved governance document status lifecycle open question; added GDR-003 (Claude Code)
- Context: User asked to tackle the "governance document status lifecycle" open item from §6.
  Investigation found the actual problem was sharper than "no lifecycle exists": the metadata
  field name "Status" was already being used for two unrelated concepts — document-level
  approval state (only ever `Draft`/`Approved` in practice) and per-rule maturity (every rule
  in `AUTH-001`, 44 occurrences, and `GOV-001`, 20 occurrences, marked `**Status:** Frozen`) —
  producing a live contradiction: both documents showed document-Status `Draft` while every
  rule inside them was `Frozen` and already cited project-wide as binding. Presented this
  finding plus three concrete decision points to the user via AskUserQuestion (separate the two
  "Status" concepts vs. unify them; 4-state vs. 5-state document lifecycle; whether to bump
  AUTH-001/GOV-001 to Approved now) rather than inventing an answer, per §6's explicit
  instruction not to resolve open governance decisions unilaterally.
- Decision/Outcome: User chose the recommended option on all three. Implemented as `GDR-003`:
  (1) renamed the per-rule field from `Status` to `Rule Maturity` in `AUTH-001` (44 occurrences)
  and `GOV-001` (20 occurrences), no value/content change; (2) added `GOV-LIFE-006 — Governance
  Document Status Lifecycle` to `GOV-001` §5, defining `Draft → Review → Approved →
  Superseded/Retired` (4 states — deliberately no document-level `Frozen`, since that term
  already means the whole Governance Baseline and, now, Rule Maturity); (3) added `Document
  Status` and `Rule Maturity` definitions to `GOV-001` §3 and a matching `Rule Maturity`
  definition to `AUTH-001` §3, cross-referencing GDR-001's separate "Decision Status" and
  AUTH-001's separate REF-document Status (AUTH-META-002) so all four "status"-shaped concepts
  in the project are now distinguishable; (4) advanced `AUTH-001` and `GOV-001` document-level
  Status from `Draft` to `Approved` (both bumped to v1.1.0 with revision-history entries).
  Updated `docs/00_Project_Governance/GDR/README.md` with the new `GDR-003` entry, and this
  file's §6/§13 to mark the open question resolved.
- Follow-up: none outstanding on this item. The two remaining "Open governance decisions" in §6
  (authority-role relationships; Non-Compliance vs "Non-Conformity" terminology) are unchanged
  and still need an explicit human decision before being written into any doc.

### 2026-08-13 — Verified entire six-doc governance correction sequence already applied (Claude Code)
- Context: User asked to work on "the governance-doc correction sequence (GOV-001)" next,
  following §6's documented order. Before editing GOV-001, checked its live git history and
  content per the §6 working rule and the project's live-state-wins principle — same pattern
  that had just caught the AUTH-001/REF-MS memory drift in the entry directly below.
- Decision/Outcome: Found that **all seven documents in the sequence already have real fix
  commits applied**, not just GOV-001: `AUTH-001` (`a3198b3`, `5ec61c0`), `GOV-001` (`46b5c5c`
  — GDR hierarchy fixed to cross-cutting), `GOV-002` (`bfba73c` — orphan `GOV-DATA-005`
  removed), `GOV-003` (`e0d554a`), `GOV-004` (`c40a3c9`), `GOV-005` (`11517a5` — "Impact
  Assessment" terminology), `GDR-001` (`4e13b8b` — "Decision Identifier" terminology,
  `GDR-DEC-004`/`GDR-DATA-005` distinction). Spot-checked file content (not just commit
  messages) for GOV-002, GOV-005, and GDR-001 to confirm the actual text matches what each
  correction required — all confirmed correct. Rewrote §6's "Confirmed corrections" list from a
  pending-task framing into a done/verified list with commit hashes, and reframed the "Working
  rule" as applying to future governance edits rather than a sequence still in progress.
- Follow-up: the sequence itself needs no further work. The three "Open governance decisions"
  items in §6 (authority-role relationships, doc status lifecycle, non-compliance terminology)
  remain genuinely unresolved and are the natural next governance-doc work if the user wants to
  continue in this area.

### 2026-08-13 — Verified AUTH-001 REF-MS gap already closed; corrected stale memory (Claude Code)
- Context: User asked to address "the AUTH-001 REF-MS family gap" flagged in §3/§13 (AUTH-001
  allegedly had no definition of the `REF-MS-XXX` family despite every `REF-MS-*` doc citing it).
  Before proposing any AUTH-001 edit, read the live file per the §6 working rule and per this
  file's own instruction (live repo state wins over what's written here).
- Decision/Outcome: The gap was **already resolved** — commit `5a81f99 "docs(auth,gdr):
  establish REF-MS authoritative reference family"` (already merged into `develop` via the
  `a37c2b8` merge, prior to this session) added `AUTH-ID-002A — New REF Family Creation` to
  AUTH-001 §7 (general rule: a distinct, separately-registered governing entity gets its own
  dedicated REF family rather than extending `REF-00X`) plus a `REF-MS` row in Appendix B, both
  backed by a new `GDR-002` decision record (background/rationale/alternatives/impact
  assessment, Approved 2026-08-12). No AUTH-001 edit was needed this session — just verification
  that the fix landed and correction of this file's now-stale open-item flags (§3, §13).
- Follow-up: none outstanding on this item. §13's `AUTH-001`/`REF-MS` bullet marked resolved
  with a pointer to this entry.

### 2026-08-12 — Committed, pushed, and merged the Mahila Sangha REF corpus + doc refresh into develop (Claude Code)
- Context: Follow-on from the drift-check entry directly below. User asked to commit and push,
  then to merge `feature/ref-documentation` into `develop`.
- Decision/Outcome: Staged and committed everything from the prior entry (the `MAHILA_SANGHA/`
  REF-MS corpus + all documentation fixes) as `a2e6a6a "docs(ref): add Mahila Sangha REF-MS
  corpus, refresh docs to match"` on top of `a9cd4bc`, pushed `feature/ref-documentation` to
  `pie`. Confirmed via `git log`/`git fetch` that `develop` had not advanced past the common
  ancestor `26dfed9`, so merging was a clean fast-forward (no conflicts) — checked out `develop`,
  fast-forwarded to `a2e6a6a`, pushed to `pie`. Both branches and their `pie/` remotes are now
  identical.
- Follow-up: none outstanding from this step. Carried-forward open items: (1) add a `REF-MS`
  family definition to `AUTH-001` in a future governance-doc session (§13), (2) decide the next
  feature branch per the §4 branch policy now that `feature/ref-documentation`'s work is merged.

### 2026-08-12 — Mahila Sangha REF corpus drift check, re-ran document-project (Claude Code)
- Context: User ran `/document-project` again. Live `git status` showed the working tree had
  moved since the last pass: commit `a9cd4bc` added the full `MAHILA_SANGHA/` REF corpus (22
  `REF-MS-XXX` documents, Sections A–M) and small "Repository Path" metadata fixes to
  `REF-001`/`REF-002`/`REF-003-C`/`REF-003-C(i)(1)`, still sitting as uncommitted/untracked
  changes on `feature/ref-documentation` (1 commit ahead of `pie/feature/ref-documentation`).
  Backend/database code was untouched (`git diff --stat` confirmed changes were scoped to
  `docs/01_Authoritative_References/`) — no backend-facing drift to check this round.
- Decision/Outcome: Updated stale "planned"/"not yet added" claims about `MAHILA_SANGHA/` in
  `docs/01_Authoritative_References/NSS/README.md` and `BY-LAW/README.md` (both had said it
  wasn't added yet — it now is, 22 documents). Added a full `MAHILA_SANGHA/` detail subsection
  to `docs/PROJECT_DOCUMENTATION.md` (mirroring the existing `NSS/` detail subsection) and fixed
  its directory-structure tree to show `MAHILA_SANGHA/` as a sibling of `NSS/`, not nested under
  it. Refreshed this file's §3 (branch/commit state, module-docs/standards-docs/releases paths
  that had gone stale after the earlier `docs/modules/` → `docs/03_Solution/modules/` etc. move
  but were never corrected in §3 itself, and the `SECTION-A..J` typo in §5's tree — NSS's own
  corpus only runs A–I, no Section J).
- Key finding worth carrying forward: **`AUTH-001` doesn't yet define the `REF-MS` identifier
  family.** Every `REF-MS-*` document's "Related Governance" section cites `AUTH-001` as the
  source of the `REF-MS-XXX` naming scheme, but `AUTH-001`'s current text has no such
  definition — flagged in `docs/PROJECT_DOCUMENTATION.md` Open questions and §13 below, not
  fixed here since `AUTH-001` changes go through the controlled process in §6, and this was a
  documentation-refresh pass, not a governance-doc edit.
- Follow-up: superseded by the entry directly above — this work has since been committed,
  pushed, and merged into `develop`.

### 2026-08-12 — Merged feature/ref-renaming + feature/founder-heritage into develop; synced most other branches; re-ran document-project (Claude Code)
- Context: User asked to push `feature/ref-renaming` into `develop` and sync every other
  branch to latest `develop`.
- Decision/Outcome: Merged `feature/ref-renaming` into `develop` (one real conflict —
  `docs/PROJECT_DOCUMENTATION.md`, existed independently on both branches; kept this session's
  rewrite after confirming via `git log`/`git merge-base` that it was a deliberate, newer
  supersession of the `feature/ref-documentation` version, not lost work — same pattern
  confirmed separately for the old flat-path `AUTH-001` file, which `develop` still had
  untouched from 2026-07-19 while `feature/ref-renaming`'s lineage had deliberately rewritten
  and moved it on 2026-07-25). Fast-forwarded `feature/admin-setup`, `feature/person-ddl`,
  `feature/person-management`, `feature/ref-documentation` to `develop` (lossless, already
  fully merged). Merged `develop` into `feature/founder-heritage` (2 unique commits) and
  `feature/membership-design` (1 unique commit) to preserve their work while catching them up.
  Left `main` untouched (advances only via the documented tag+release process). User then asked
  specifically about merging `feature/founder-heritage` (real `Founder` singleton model, no
  views/URLs yet) and `feature/membership-design` (a single DRAFT overview doc, not yet at the
  ERD/business-rules/table-design maturity `organization`/`person` reached) into `develop` —
  approved `founder-heritage`, held back `membership-design` as not yet "complete & verified"
  per the branch policy in §4. Fast-forwarded `develop` to include `heritage`, added the missing
  `backend/heritage/` + `backend/heritage/migrations/` READMEs, fixed stale "heritage doesn't
  exist yet" claims in `backend/README.md` and `docs/03_Solution/modules/heritage/README.md`,
  then re-ran `/document-project` on `develop` to catch remaining drift (this entry + the
  `heritage` corrections in `docs/PROJECT_DOCUMENTATION.md` and §8 above).
- Follow-up: `feature/membership-design` still needs proper module design docs
  (`01_design`/`02_erd`/`03_business_rules`/`04_table_design`) before it's mergeable per the
  project's own module-maturity pattern. `backend/heritage/` has no `urls.py`/views yet, and the
  module's Biography/Philosophy/Teachings/Publications scope beyond the `Founder` singleton is
  still undesigned.

### 2026-08-12 — document-project skill updated to auto-create per-folder READMEs, re-run (Claude Code)
- Context: Previous doc-refresh pass (below) only flagged folders missing a `README.md`
  rather than creating them. User asked to change that behavior in the `document-project`
  skill itself and re-run.
- Decision/Outcome: Edited `~/.claude/skills/document-project/SKILL.md` step 4 to create a
  scoped `README.md` for any non-trivial folder/module lacking one (skipping trivial/empty
  folders), instead of just noting the gap. Re-ran the skill: created READMEs for `backend/`,
  `backend/{config,authentication,dashboard,foundation,family,membership}/`, `database/`,
  `docs/`, `docs/01_Authoritative_References/NSS/`,
  `docs/00_Project_Governance/{AUTH,GOV,GDR,STD}/`,
  `docs/03_Solution/modules/organization/`, `docs/05_Releases/`. Skipped `backend/attendance/`
  and `backend/governance/` (pure stubs), `backend/static/`+`backend/templates/` (asset dirs,
  already covered in `docs/PROJECT_DOCUMENTATION.md`), and the empty `docs/03_Solution/
  {api,architecture,database,infrastructure,security,ui}/`, `docs/02_Requirements/`,
  `docs/04_Testing/` scaffolding.
- Follow-up: none — this is a completed mechanical pass. If new non-trivial folders are added
  later, re-running `/document-project` should pick them up per the updated skill instructions.

### 2026-08-12 — Doc folder consolidation + full documentation refresh (Claude Code)
- Context: Continuing folder-renaming work on `feature/ref-renaming`. `docs/standards/` and
  `docs/modules/` had already been git-moved into `docs/00_Project_Governance/STD/` and
  `docs/03_Solution/modules/` respectively; `docs/releases/` into `docs/05_Releases/`. A staged
  rename had accidentally nested `docs/modules/{organization,person}` under
  `docs/03_Solution/modules/modules/` instead of directly under `docs/03_Solution/modules/`.
  Then ran `/document-project` to generate a comprehensive standalone doc and refresh existing
  markdown files against actual code.
- Decision/Outcome: (a) Fixed the nesting — removed the empty placeholder dirs, `git mv`'d
  `organization`/`person` up one level, confirmed via `git status`. (b) Read the actual backend
  code and DDL (agents explored `backend/`, `database/ddl`, `database/seed`,
  `docs/00_Project_Governance`, `docs/03_Solution/modules`) and found several stale claims: this
  file's §5 doc-tree diagram and §8 Django app list were both wrong (§8 said `backend/apps/...`;
  real apps live directly under `backend/`, and `dashboard`/`governance`/`attendance` aren't in
  `INSTALLED_APPS`); this file's §8 DB-naming claim of `_id` for business identifiers doesn't
  match the SQL, which uses `_code` throughout. Corrected both in §8/§5 above. Created
  `docs/PROJECT_DOCUMENTATION.md` as the full code-verified reference. Fixed a stale index list
  in `docs/03_Solution/modules/person/04_person_table_design.md` (leftover `district_pk`/
  `state_pk`/`country_pk` from an older address design, not matching the actual implemented
  `person_address` table) and updated its module `README.md` status line (SQL implementation is
  actually done, not "in progress"). Updated root `README.md`'s repository-structure and
  release-notes-path sections to match the post-rename layout.
- Key finding worth carrying forward: **Organization module is fully designed
  (`docs/03_Solution/modules/organization/`) but has zero SQL implementation** —
  `database/ddl/02_organization/*.sql` are all 0-byte placeholder files. Person module design
  and SQL match closely. Also: Django ORM models (`foundation.Person`, `foundation.Organization`)
  and the SQL DDL schema (`person`, `organization` tables) are two separate, unreconciled designs
  right now — see `docs/PROJECT_DOCUMENTATION.md` Architecture/Gotchas for detail.
- Follow-up: next session should decide whether to (1) implement `database/ddl/02_organization/`
  against the existing design docs, or (2) reconcile the Django ORM models with the SQL DDL
  track before building more on either. Neither decision was made this session — flagged only.

### 2026-08-11 — Full project handoff ingested (3 phases) + live repo verification (Enchanté)
- Context: User provided a 3-phase project handoff (originally written for a fresh-chat
  continuation), migrated from a Windows machine (`D:\Important\NSS\NSS_ERP`) to this Mac repo.
  Phase 3 was explicitly marked as the "updated" version, superseding Phases 1–2 where they
  conflict (esp. current branch, AUTH-001 status, REF-003 progress).
- Decision/Outcome: Cross-checked all three phases against **live git state** rather than
  trusting the handoff text at face value (per the handoff's own stated rule). Found: (a)
  current branch is `feature/ref-renaming` as Phase 1/3 state, not `feature/organization-module`
  as Phase 2 stated (that was a stale snapshot); (b) AUTH-001 already has a correction commit,
  more progressed than Phase 3 assumed; (c) REF-003 series is complete through Section J
  (17 documents), far beyond "stopped at Advisory Board" — good news, not previously reflected
  in any handoff phase. Consolidated all frozen architecture, governance doc-review findings,
  open governance-terminology questions, and module/schema state into this file (§1–§11).
- Follow-up: Next actual work session should (1) open and read the current AUTH-001 file to
  confirm whether the structural corrections in §6 are already applied, and (2) decide whether
  to continue the governance-doc correction sequence (GOV-001 next) or pivot to REQ-generation
  now that REF-003 looks substantially complete. Flag to user: several terminology/authority
  questions in §6 still need an explicit human decision before being written into GOV/GDR docs.

### 2026-08-11 — Shared memory file initialized (Enchanté)
- Context: User wants decisions/context to persist across both Claude (VS Code) and Enchanté
  conversations for this repo, instead of being siloed per tool.
- Decision/Outcome: Created this `CLAUDE.md` at repo root as the shared, human-readable memory
  file. Claude Code reads `CLAUDE.md` automatically; Enchanté reads/updates it whenever this
  project path is referenced, and holds a pointer to it in its own persistent memory.
- Follow-up: Populate with real project decisions as they come up (now superseded by the
  handoff-ingestion entry above).

## 13. Open Questions

- ~~Governance Authority vs Decision Authority vs Approving Authority vs Project Owner vs
  Project Steering Committee~~ — **resolved 2026-08-14**, see §6/§12/GDR-004.
- ~~Governance document status lifecycle~~ — **resolved 2026-08-13**, see §6/§12/GDR-003.
- ~~Mahila Parichalana Mandali exact composition/election/term~~ — **resolved 2026-08-14**:
  confirmed by project owner that every Sakha Sangha has its own local Mahila Sangha
  (per `REF-001` Clause 12), and all of these are governed centrally by one Mahila Parichalana
  Mandali. The `REF-MS-*` corpus is that central Mandali's own Bye-Law — `REF-MS-6(i)`–
  `REF-MS-6(viii)` define the Mandali's own governing structure. See §7/§12.
- Final conceptual schema table count — genuinely open, ranges 88–130+ depending on
  unresolved operational modules (§8, §10).
- ~~`AUTH-001` has no definition of the `REF-MS-XXX` identifier family~~ — **resolved**, see §12
  2026-08-13 entry: `AUTH-ID-002A` + Appendix B row added, backed by `GDR-002`.
