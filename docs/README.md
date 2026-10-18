# docs/

See **`PROJECT_DOCUMENTATION.md`** in this folder for the full, code-verified project reference
(architecture, setup, workflows, gotchas). This file is just an index of what's under `docs/`.

| Folder | Contents |
|---|---|
| `00_Project_Governance/` | Governance framework (`AUTH/`, `GOV/`, `GDR/`) and concrete engineering standards (`STD/`) |
| `01_Authoritative_References/` | Source-faithful transcription of NSS's Constitution & Bye-Laws (NSS, Mahila Sangha); `CIRCULARS/`, `NOTIFICATIONS/`, `RESOLUTIONS/` awaiting source material |
| `03_Solution/` | 22 module design docs (`modules/`), `architecture/` (incl. `GETTING_STARTED.md`, `DEPLOYMENT_PROCEDURE.md`, `MEMBER_DASHBOARD.md`), `standards/`, `infrastructure/`, `database/` (cross-module conventions), `security/` (architecture map + per-tier audits through `TIER5_SECURITY_AUDIT.md`; no Tier 6 audit yet), `ui/` (13 mockups), `code_explanations/` (per-layer walkthroughs); `api/` holds per-tier contract docs (Bootstrap, Foundation, Organization, Person) plus a consolidated `API_CONTRACT.md` covering all tiers (201 endpoints across 15 routers, incl. the Tier 5 auth/admin/registration/claims/audit routers and the Tier 6 governance, membership-change-request and correspondence routers) — the Tier 5 work itself is released in v0.11.0 |
| `05_Releases/` | Release notes, v0.1.0 → v0.10.4, each with its own file (latest released tier: Tier 4 Family + Membership; Tier 5 Authentication + Administration is released as v0.11.0; Tier 6 Governance is in progress, not yet tagged — no `v0.11.0.md` yet) |
