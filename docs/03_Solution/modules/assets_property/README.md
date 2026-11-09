# Assets & Property Module

Solution-layer design for Assets & Property — Module #22, the physical/administrative record of
NSS movable and immovable property and assets (identification, registration, custody,
maintenance, and lifecycle). Five files, `v1.0.0 DRAFT — SOURCE ALIGNED`
(document-level `Status` field remains `DRAFT` throughout, same content-freeze convention as
every other SOURCE ALIGNED module — this is not a lifecycle "FROZEN" promotion).

## Documents

| # | File | Document ID | Covers |
|--:|------|--------------|--------|
| 1 | `01_assets_property_module_overview.md` | `SOL-AP-001` | Purpose, scope boundaries, module acceptance (`ASSET-ARCH-001`) |
| 2 | `02_assets_property_erd.md` | `SOL-AP-002` | Entity-relationship design — `Property`/`Asset` as primary entities plus `Custodianship`, `Statutory Record`, `Maintenance Record` |
| 3 | `03_assets_property_lifecycle.md` | `SOL-AP-003` | Three state machines: Property, Asset, Custodianship |
| 4 | `04_assets_property_business_rules.md` | `SOL-AP-004` | Business rules `AP-001`–`AP-074` (24 CONSTITUTIONAL, 32 ERP, 13 CROSS-MODULE, 5 PENDING) |
| 5 | `05_assets_property_table_design.md` | `SOL-AP-005` | Table design — 7 module-owned tables |

## Tables (7)

`property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`,
`property_document`, `asset_document`.

The ERD document (`02_assets_property_erd.md`) lists only the 5 "minimum source-derived" tables
(everything but the two document-junction tables) — `property_document`/`asset_document` were
added at the Table Design stage to implement the Foundation `document_master` linkage.

## Key design points

- **Property vs. Asset are separate entities** — Property covers immovable/land-and-building
  holdings; Asset covers movable items; `Custodianship` tracks who currently holds an Asset
  (transfer creates a new custodianship record, preserving history rather than overwriting it).
- **Scope boundaries are explicit** — this module does not own financial transactions or
  depreciation (Finance, per `FIN-ARCH-001`), acquisition/disposal *approval* (Governance —
  this module records the event, not the authorization), historical/cultural significance
  (Heritage — same physical entity, e.g. Nilachala Kutir, may be referenced from both modules
  without duplicating records), or organizational hierarchy (Organization).
- **Foundation document registry, not a local one** — `property_document`/`asset_document` are
  junction tables to Foundation's shared `document_master` (`DOC-ARCH-001`), not a
  module-local document table — consistent with how Person/Heritage/Publications also consume
  `document_master` rather than each owning their own.
- **Depends only on Foundation + Person + Organization** — no hard FK to Finance or Membership;
  per `docs/03_Solution/architecture/IMPLEMENTATION_DEPENDENCY_ORDER.md`, this module sits at
  **Tier 6** (alongside Attendance and Governance) and could be created as early as Phase 4 per
  `FK_DEPENDENCY_GRAPH.md`.
- **One open item (AP-066):** whether "sacred articles" fall under this module's Asset custody
  model or Heritage's cultural-significance model is explicitly flagged PENDING, not resolved.

## Backend/DDL reality

**Backend implemented 2026-11-02 and admin UI added 2026-11-02; committed on `feature/tier6-governance` (not yet merged to `develop`). The backend suites ran in the owner's full DB run (2026-11-04/05); the admin UI has never been opened in a browser.** Implementation
decisions for the PENDING items and every interpretation made are recorded in
`docs/00_Project_Governance/GDR/GDR-010_Assets_and_Property_Implementation_Decisions.md` (status `Proposed` — owner
approval pending). The design documents above are unchanged.

| Layer | Where |
|---|---|
| DDL (7 tables + guard triggers) | `database/ddl/11_assets_property/` (build Phase 11g of `02_build.sh`/`.ps1`/`render_build.sh`; 78 tables with this module; 79 with the live-refresh marker table) |
| Reference data | `database/seed/11_assets_property/01_assets_property_reference_data_patch.sql` — `PROPERTY` (`PROP<n>`) / `ASSET` (`AST<n>`) id sequences, 7 master categories (incl. `ACQUISITION_METHOD`), 38 values (incl. `DISPOSED`/`RETIRED` end reasons; idempotent patch: the Foundation seeds are existence-gated) |
| RBAC | `database/seed/00_bootstrap/05_assets_property_permissions_patch.sql` — `ASSET_VIEW` / `ASSET_MANAGE` + 12 grants (28 → 30 permissions, 166 → 178 mappings; owner decisions 2026-11-02: Anchalika/Zilla admins view-only, Mahila admin none); `06_assets_property_permissions_revoke_patch.sql` soft-deletes the 4 grants an earlier version of `05` created. Optional "belongs to" column: `database/ddl/11_assets_property/10_assets_property_belongs_to_patch.sql`; optional acquisition-method column: `11_assets_property_acquisition_method_patch.sql`; `12_assets_property_terminal_custody_patch.sql` ENDs the ACTIVE custodianship of already DISPOSED/RETIRED records |
| API | `api/routers/assets_property.py` + `api/schemas/assets_property.py` — 26 endpoints under `/api/v1/assets-property` (contract: `docs/03_Solution/api/API_CONTRACT.md` §12g) |
| Admin UI | `frontend/admin.html` sidebar group "Assets & Property" (Properties `#properties` / Assets `#assets`; one shared panel) + `frontend/assets/js/assets-property.js` (mixin on `adminPanel()`); status/lifecycle labels and tables `NSS.ASSET_PROPERTY_*` in `nss-config.js`, badges `badge-ap-*` in `badges.css`. Gated by `ASSET_VIEW` (read) / `ASSET_MANAGE` (every write control); UI tests `tests/ui/test_ui_assets_property.py` (83, source parsing) |
| Tests | `tests/db/test_assets_property_schema.py`, `tests/api/test_assets_property.py`, `tests/security/test_assets_property_security.py` (+ `tests/assets_property_support.py`) — 665 collected (incl. the parity file) |

How the design maps to the implementation:

- **Property vs. Asset** — separate tables, ids `PROP<n>` / `AST<n>` (AP-005/007/008), immutable.
- **Lifecycle** — fixed `status` CHECKs; transitions per SOL-AP-003 enforced in the API and by DB triggers; first
  custodian advances REGISTERED → ACTIVE / IN_CUSTODY; transfers never change status; DISPOSED / RETIRED terminal.
- **Custodianship** — temporal table, XOR target, one ACTIVE per record (partial unique indexes), transfer = ENDED row
  + new ACTIVE row, ENDED rows immutable (AP-017/018/042/072); end reason (master data) distinguishes dissolution /
  vesting (AP-058/059).
- **PENDING items** — property/asset type, end reason and document relationship are admin-extendable master data
  (candidate values seeded); holding arrangement (AP-013), location (AP-022) and condition are free text; maintenance
  scheduling (AP-032), valuation (AP-063) and the sacred-article mechanism (AP-066) are not implemented.
- **Authorization** — `ASSET_VIEW` / `ASSET_MANAGE` + admin scope on the record's EFFECTIVE custodian organization (the active one; for a DISPOSED/RETIRED record the LAST one, see below); a
  record with no effective custodian is global-authority only; a transfer needs scope over both organizations (AP-074).
  `ASSET_MANAGE`: ADMIN / KENDRA / SAKHA / PATHA_CHAKRA admins; Anchalika / Zilla admins, Auditor and Report Viewer are
  view-only; the Mahila admin has none.
- **Belongs to** — optional `belongs_to_organization_pk` (any active organization) distinct from the custodian;
  informational only, never affects authorization, scope, the custodian rule or the lifecycle (GDR-010 §2D).
- **Acquisition method** — optional `acquisition_method_code` (master data `ACQUISITION_METHOD`: how the record was acquired, AP-023); informational only (GDR-010 §2E, owner decision 2026-11-03).
- **Disposal / retirement closes custody** — DISPOSED / RETIRED END the active custodianship in the same transaction (end reason `DISPOSED` / `RETIRED`); the record keeps showing its last custodian (`custodian_is_last`) and stays visible to the same admins (GDR-010 §2F, owner decision 2026-11-03).
- **Boundaries** — no financial columns or tables (Finance), no approval tables (Governance records the decision;
  Assets & Property only records the event), documents only through `document_master` junctions.

## Not yet reconciled

The `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` and
`docs/03_Solution/security/SECURITY_ARCHITECTURE.md` cross-module consolidation docs don't list
this module's tables in their source inventory. Not a contradiction, just an update those docs
haven't caught up to yet, same gap already noted in Finance's own README.
