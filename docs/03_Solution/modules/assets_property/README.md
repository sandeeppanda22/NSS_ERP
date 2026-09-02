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

No corresponding `backend/` Django app and no `database/ddl/` implementation — design only,
same as every other module except membership/family/heritage.

## Not yet reconciled

The `docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md` and
`docs/03_Solution/security/SECURITY_ARCHITECTURE.md` cross-module consolidation docs don't list
this module's tables in their source inventory. Not a contradiction, just an update those docs
haven't caught up to yet, same gap already noted in Finance's own README.
