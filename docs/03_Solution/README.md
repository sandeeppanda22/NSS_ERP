# docs/03_Solution/

Solution-layer design docs: per-module design (`modules/`) plus cross-cutting design areas.

| Folder | Status |
|---|---|
| `modules/` | 22 module folders, each with a complete or largely-complete design doc set (`programmes_events/` still v0.1.0 DRAFT/not frozen; `assets_property/` is the 22nd) — see `modules/README.md` for the per-module status table |
| `architecture/` | 16 files, incl. `GETTING_STARTED.md`, `MEMBER_DASHBOARD.md`, `PERFORMANCE_TUNING.md` and the `README.md` index, plus cross-module architecture docs: `TECH_STACK_DECISIONS.md` (v1.3, approved tech decision record — FastAPI is now the sole backend framework, Django removed), `DEVELOPER_REFERENCE_GUIDE.md`, `BOOTSTRAP_ARCHITECTURE.md`, `CROSS_MODULE_PRINCIPLES.md`, `DDL_CREATION_ORDER.md`, `FK_DEPENDENCY_GRAPH.md`, `MODULE_DEPENDENCY_MAP.md`, `IMPLEMENTATION_DEPENDENCY_ORDER.md`, `DEPLOYMENT_PROCEDURE.md`, plus 4 Programmes & Events docs (`PROGRAMME_EVENT_DOMAIN_MODEL.md`, `EVENT_ENTITY_RECONCILIATION.md`, `PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md`, `PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md`) — see `architecture/README.md` for the per-file status table. API contracts and code-explanation walkthroughs have both moved out of this folder to their own siblings: `docs/03_Solution/api/` and `docs/03_Solution/code_explanations/` |
| `database/` | `DATABASE_DESIGN_STANDARDS.md` (`SOL-DB-001`) — cross-module DB conventions consolidation |
| `security/` | `SECURITY_ARCHITECTURE.md` (`SOL-SEC-001`) — security ownership/routing map, plus per-tier security audits (`TIER0`-`TIER5_SECURITY_AUDIT.md`, `SECURITY_AUDIT_TIER0_4.md`; no Tier 6 audit yet) |
| `standards/` | `lifecycle/` — `SOL-LIFE-001`/`SOL-LIFE-002`, both FROZEN v1.0.0 |
| `infrastructure/` | `DEPLOYMENT_SYNC_PLAN.md` — deployment/repo-sync plan |
| `ui/` | `mockups/` — 13 numbered static HTML mockups (Tailwind + DaisyUI via CDN) plus `status_badge_preview.html` |
| `api/` | 5 API contract docs — per-tier Bootstrap/Foundation/Organization/Person plus the consolidated cross-tier `API_CONTRACT.md` (Tiers 0-6 incl. Attendance and Sakha re-parent approvals, 251 endpoints across 17 routers) — for the FastAPI code running at the root-level `api/` folder; see `api/README.md` for the per-file list |

See `docs/PROJECT_DOCUMENTATION.md` → `03_Solution/` detail for the full code-verified
breakdown of every file in each folder.
