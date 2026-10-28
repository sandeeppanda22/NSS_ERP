# docs/

See **`PROJECT_DOCUMENTATION.md`** in this folder for the full, code-verified project reference
(architecture, setup, workflows, gotchas). This file is just an index of what's under `docs/`.

| Folder | Contents |
|---|---|
| `00_Project_Governance/` | Governance framework (`AUTH/`, `GOV/`, `GDR/`) and concrete engineering standards (`STD/`) |
| `01_Authoritative_References/` | Source-faithful transcription of NSS's Constitution & Bye-Laws (NSS, Mahila Sangha); `CIRCULARS/`, `NOTIFICATIONS/`, `RESOLUTIONS/` awaiting source material |
| `03_Solution/` | 22 module design docs (`modules/`), `architecture/` (incl. `GETTING_STARTED.md`, `DEPLOYMENT_PROCEDURE.md`, `MEMBER_DASHBOARD.md`), `standards/`, `infrastructure/`, `database/` (cross-module conventions), `security/` (architecture map + per-tier audits through `TIER5_SECURITY_AUDIT.md`; no Tier 6 audit yet), `ui/` (13 mockups), `code_explanations/` (per-layer walkthroughs); `api/` holds per-tier contract docs (Bootstrap, Foundation, Organization, Person) plus a consolidated `API_CONTRACT.md` covering all tiers (241 endpoints across 16 routers, incl. the Tier 5 auth/admin/registration/claims/audit routers, the Tier 6 governance, membership-change-request and correspondence routers and the Tier 6 attendance router) — the Tier 5 work itself is released in v0.11.0 |
| `05_Releases/` | Release notes, v0.1.0 → v0.10.4, each with its own file (latest released tier: Tier 4 Family + Membership; Tier 5 Authentication + Administration is released as v0.11.0; Tier 6 Governance/Correspondence/Attendance are unreleased, on `feature/tier6-governance`; `v0.11.0.md` exists for Tier 5) |
