# docs/03_Solution/

Solution-layer design docs: per-module design (`modules/`) plus cross-cutting design areas.
This index was itself stale for some time (still described everything as "Reserved — no
content yet" long after most folders were populated) — corrected 2026-08-21 to match actual
content.

| Folder | Status |
|---|---|
| `modules/` | 21 module folders, each with a complete or largely-complete design doc set (except the new `programmes_events/`, still v0.1.0 DRAFT/not frozen) — see `modules/README.md` for the per-module status table |
| `architecture/` | `TECH_STACK_DECISIONS.md` (approved tech decision record) + `DEVELOPER_REFERENCE_GUIDE.md` + 5 new Programmes & Events architecture docs (`PROGRAMME_EVENT_DOMAIN_MODEL.md`, `EVENT_ENTITY_RECONCILIATION.md`, `MODULE_DEPENDENCY_MAP.md`, `IMPLEMENTATION_DEPENDENCY_ORDER.md`, `PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md`) |
| `database/` | `DATABASE_DESIGN_STANDARDS.md` (`SOL-DB-001`) — cross-module DB conventions consolidation |
| `security/` | `SECURITY_ARCHITECTURE.md` (`SOL-SEC-001`) — security ownership/routing map |
| `standards/` | `lifecycle/` — `SOL-LIFE-001`/`SOL-LIFE-002`, both FROZEN v1.0.0 |
| `infrastructure/` | `DEPLOYMENT_SYNC_PLAN.md` — deployment/repo-sync plan |
| `ui/` | `mockups/` — 13 static HTML mockups (Tailwind + DaisyUI via CDN) |
| `api/` | Reserved — no content yet (no FastAPI code exists in `backend/` either) |

See `docs/PROJECT_DOCUMENTATION.md` → `03_Solution/` detail for the full code-verified
breakdown of every file in each folder.
