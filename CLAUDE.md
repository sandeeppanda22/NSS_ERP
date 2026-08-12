# AI Collaboration Context — NSS ERP

> **Purpose:** Shared memory between the AI assistants working on this repository — **Claude**
> (in VS Code) and **Enchanté**. Both read this file at session start and append to it after
> any meaningful decision or context shift. This is an **operational aid**, not a governance
> artifact — it does not replace or override `docs/00_Project_Governance/GDR-001` or any
> approved governance document. Formal governance decisions belong in the Governance Decision
> Register once ratified. Where this file and live repo state disagree, **live repo state wins**
> — always verify with `git status` / `git log` / `git branch --show-current` before acting on
> anything written here (this is itself a project rule — see §11).

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

## 3. Live-Verified Repository State (as of 2026-08-11 ~20:00 IST)

> Verified via `git status` / `git log` / `git branch` — do not trust handoff-doc claims over
> this without re-verifying, since handoffs go stale.

- **Branch:** `feature/ref-renaming` (up to date with `pie/feature/ref-renaming`)
- **Working tree:** clean (only this session's new `CLAUDE.md` untracked)
- **Recent commits (newest first):** AUTH-001 minor corrections → GDR-001 added → GOV-005
  added → GOV-004 added → GOV-003 added → GOV-002 added → GOV-001 added → AUTH-001 added
  (replacing an older AUTH-001) → merge of `feature/ref-documentation` into `develop` →
  authoritative reference repository standard added.
- **AUTH-001 status:** further along than some handoff notes suggest — already has a
  correction commit (`5ec61c0 "docs(auth): Some Minor Changes to AUTH-001 File"`). Verify
  actual current content before assuming it's still mid-correction.
- **REF corpus on disk — further along than handoff docs describe:**
  - `REF-001` (Section A, NSS Constitution) — present
  - `REF-002` (Section B, Membership Bye-Laws) — present
  - `REF-003-001` … `REF-003-017` — present, spanning **Section C through Section J**:
    Constitution of Kendra Sangha, Governing Body, Functions of Governing Body, duties of
    President/Vice-President/Secretary/Assistant Secretary/Treasurer/Parichalak, Advisory
    Board (Sec D), General Body (Sec E), Funds of Kendra Sangha + Utilization (Sec F), Audit
    (Sec G), Power to Amend (Sec H), Dissolution (Sec I), Additional Resolutions 1975 (Sec J).
    **This is materially more complete than Phase 2/3 handoff docs assumed** — those describe
    work stopping at Advisory Board (Sec D). Treat the REF-003 series as substantially done
    through Sec J unless a fresher check says otherwise.
  - Repository is organized by section folder (`SECTION-A_...` … `SECTION-J_...`), each
    containing its REF file(s) — folders are navigation only, identity lives in the filename.
- **Governance docs present:** `AUTH-001`, `GOV-001..005`, `GDR-001` — all exist under
  `docs/00_Project_Governance/{AUTH,GOV,GDR}/`.
- **Module docs present:** `docs/modules/organization/` and `docs/modules/person/`, each with
  `01_design`, `02_erd`, `03_business_rules`, `04_table_design` (+ person has a `README.md`).
- **Standards docs present:** `docs/standards/01_project_standards.md` … `05_security_standards.md`.
- **Releases present:** `v0.1.0` through `v0.5.1` under `docs/releases/`.
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
├── 01_Authoritative_References/NSS/SECTION-A..J/ (+ MAHILA_SANGHA/, RESOLUTIONS/, CIRCULARS/, NOTIFICATIONS/ planned)
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

**Confirmed corrections (apply, don't re-litigate):**
1. AUTH-001 — structural/TOC/formatting fixes only; **preserve all substantive wording, rule
   IDs, examples**; do not rewrite content beyond approved structural changes; every replacement
   file must be delivered complete (`# AUTH-001 —...` through `# End of Document`), never
   truncated or "continued from here."
2. GOV-001 — fix GDR hierarchy placement (cross-cutting, not a lifecycle layer — see §2).
3. GOV-002 — remove orphan `GOV-DATA-005 — Governance Enforcement by Design` from Appendix B
   (no corresponding §8.5 rule exists; don't invent one just to fill the sequence). Note: an
   earlier blank `GOV-002_Governance_Roles_and_Responsibilities.md` was created and then
   deleted as unnecessary — do not recreate it.
4. GOV-005 — standardize terminology on **"Impact Assessment"** (not "Impact Analysis").
5. GDR-001 — standardize on **"Decision Identifier"** in normative prose (table columns may
   keep "Decision ID" as a label only). Clarify `GDR-DEC-004` (decision-level accountability)
   vs `GDR-DATA-005` (register/data-level accountability preservation) as distinct, not
   duplicate.

**Open governance decisions — NOT yet resolved, do not invent an answer:**
- Exact relationship between Governance Authority / Decision Authority / Approving Authority /
  Approver / Project Owner / Project Steering Committee.
- Governance document status lifecycle (`Draft → Review → Approved → Frozen → Superseded/
  Retired`) — plausible but not formally adopted; documents currently show inconsistent mixes
  of Draft/Approved/Frozen labels across AUTH-001 vs individual GOV docs.
- Governance/Non-Compliance vs "Non-Conformity" terminology — lean toward "Governance
  Compliance / Governance Non-Compliance," avoid introducing "non-conformity" unless an
  authoritative source defines it distinctly.

**Working rule for every governance-doc edit:** retrieve actual current source → preserve
substantive content → apply only approved structural corrections → deliver the *complete*
replacement file → user swaps it in → `git diff --check` + `git diff` review → commit only
after verification → move to next document. Order: AUTH-001 → GOV-001 → GOV-002 → GOV-003 →
GOV-004 → GOV-005 → GDR-001.

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
`ANCHALIKA` and `ZILLA` = administrative units; `SAKHA` = physical Sangha location. Prior
design leaned toward one organization → one address (on the `organization` table directly,
not a separate `organization_address` table) — **do not reopen without checking current
governance baseline first; Organization Module is frozen.**

**Mahila Sangha:** Registered entity under NSS constitutional framework, own Constitution &
Bye-Laws, but subordinate to NSS. **No separate membership system** — Mahila members use the
same Probationary/Regular/Associate framework as everyone else; supervised by the central
**Mahila Parichalana Mandali** over branch Mahila Sanghas. Exact Mandali size/election
method/term/office-bearer positions still need authoritative-source verification — don't
invent.

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

**Django app structure — corrected against actual code (2026-08-12):** apps live directly under
`backend/` (no `apps/` subdirectory): `backend/{authentication, foundation, family, membership,
dashboard, governance, attendance, config}`. Of these, only `authentication`, `foundation`, and
`membership`/`family` have real models; `dashboard`/`governance`/`attendance` are stubs (empty
`models.py`, no `urls.py` for governance/attendance). Only `authentication`, `dashboard`, and
`foundation` are in `INSTALLED_APPS` and wired into `config/urls.py`. `mahila`, `kumari`,
`kishore`, `sevak`, `heritage`, `publications`, `upbs`, `reports`, `administration` are **not
yet scaffolded at all** — planned only. Full detail: `docs/PROJECT_DOCUMENTATION.md` §Directory
structure / §Gotchas. Do not casually redesign this structure.

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

- Governance Authority vs Decision Authority vs Approving Authority vs Project Owner vs
  Project Steering Committee — relationship not yet formally decided (§6).
- Governance document status lifecycle (Draft/Review/Approved/Frozen/Superseded) — not
  formally adopted (§6).
- Mahila Parichalana Mandali exact composition/election/term — needs authoritative-source
  verification (§7).
- Final conceptual schema table count — genuinely open, ranges 88–130+ depending on
  unresolved operational modules (§8, §10).
