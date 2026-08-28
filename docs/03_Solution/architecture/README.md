# docs/03_Solution/architecture/

Overall solution architecture documentation (cross-module, above the per-module docs in
`docs/03_Solution/modules/`).

## Files

- **`TECH_STACK_DECISIONS.md`** — Approved technology decision record: database (PostgreSQL on
  Neon.dev), backend (Django 6.0.6 + FastAPI 0.136.3 on Render.com/Uvicorn), frontend (Tailwind
  CSS + DaisyUI + HTMX + Alpine.js, replacing Bootstrap 5), mobile/offline strategy (PWA +
  IndexedDB + Background Sync), git remotes/deployment flow, and rejected alternatives.
- **`DEVELOPER_REFERENCE_GUIDE.md`** — Per-module "which document to read before coding" matrix
  following the REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE lifecycle order.
- **`PROGRAMME_EVENT_DOMAIN_MODEL.md`** (`SOL-EVT-001`) — Domain model for Programmes & Events:
  Programme Type, Event Instance, Session, Location; Organization ≠ Location; Patha Chakra is
  an Organization Type, not an Event/Programme Type.
- **`EVENT_ENTITY_RECONCILIATION.md`** (`SOL-EVT-002`) — Reconciles the domain model above
  against UPBS, Kishor, Sevak, Mahila, Finance, and Attendance's own event-shaped entities.
- **`MODULE_DEPENDENCY_MAP.md`** (`SOL-ARCH-007`) — 21-module hard-FK/runtime/domain
  dependency map. Status: PROPOSED, not frozen.
- **`IMPLEMENTATION_DEPENDENCY_ORDER.md`** (`SOL-ARCH-008`) — 12-tier proposed build order
  across all 21 modules (Programme & Events sits at Tier 7). Status: PROPOSED, not frozen.
- **`PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md`** (`SOL-EVT-006`) — Final compatibility review
  for the new Programme & Events module (Module #21) against every other module; concludes
  "architecturally justified," no hard conflicts, but flags open ownership/migration-strategy
  risks — see `docs/03_Solution/modules/programmes_events/README.md`.

This is the **approved target**, not yet the current code — `backend/` still runs Bootstrap 5
templates with no FastAPI wiring as of this writing. The five `PROGRAMME`/`EVT`/`ARCH`
documents above are themselves still PROPOSED/DRAFT, not approved decisions like
`TECH_STACK_DECISIONS.md`. See `docs/PROJECT_DOCUMENTATION.md` → Architecture for the current
code-verified state and how it differs from these decisions.
