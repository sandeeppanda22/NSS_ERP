# NSS ERP Organization Module

Version: 1.0

Status: DRAFT — designed, **not yet implemented in SQL** (`database/ddl/02_organization/*.sql`
are all 0-byte placeholder files; see `docs/PROJECT_DOCUMENTATION.md` → Key workflows).

---

## Documents

01_organization_design.md

Purpose:
High-level Organization module design — single self-referencing `organization` table for the
Kendra → Anchalika/Zilla → Sakha → Patha_Chakra hierarchy.

---

02_organization_erd.md

Purpose:
Entity relationship design for `organization_type_master`, `organization_status_master`,
`organization`, `organization_address`.

---

03_organization_business_rules.md

Purpose:
Business rules governing the organization hierarchy (single active KENDRA root, parent-type
constraints per level, no physical delete, org code formats).

---

04_organization_table_design.md

Purpose:
Physical database table design — full column/constraint/index/seed-data spec, ready to
implement.

---

## Current Status

Design Complete

ERD Complete

Business Rules Frozen

Table Design Frozen

SQL Implementation Not Started

---

## Note

Django's `foundation.Organization` model (`backend/foundation/models.py`) is a much simpler
placeholder that predates this design (no hierarchy, no self-reference) — see
`docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas before extending it.
