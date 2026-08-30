# NSS ERP — Assets & Property Table Design

**Document ID:** SOL-AP-005
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Assets & Property
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the table-design baseline for Module #22 —
Assets & Property.

The design is derived strictly from the approved Overview (SOL-AP-001),
ERD (SOL-AP-002), Lifecycle (SOL-AP-003), and Business Rules (SOL-AP-004).

No new business concepts are introduced.

---

# 2. Source-Supported Tables

| # | Table | Responsibility | Source |
|--:|-------|---------------|--------|
| 1 | `property` | Immovable property identity and state | ERD §4, AP-001/002 |
| 2 | `asset` | Movable asset identity and state | ERD §5, AP-001/003 |
| 3 | `custodianship` | Historical custody relationship | ERD §6, AP-014–020 |
| 4 | `property_statutory_record` | Property statutory obligations | ERD §7, AP-034–040 |
| 5 | `maintenance_record` | Maintenance activity history | ERD §8, AP-027–033 |
| 6 | `property_document` | Property ↔ document_master junction | AP-067/069 |
| 7 | `asset_document` | Asset ↔ document_master junction | AP-067/069 |

## 2.1 Table Ownership Declaration

**Assets & Property OWNS (DDL authority):**

```text
property
asset
custodianship
property_statutory_record
maintenance_record
property_document
asset_document
```

**External tables CONSUMED (not owned):**

```text
organization              (Organization module)
document_master           (Foundation module)
financial_transaction     (Finance module)
```

---

# 3. Database Naming Standard

The project standard uses:

```text
<table_name>_pk
```

for technical primary keys. Therefore:

```text
property_pk
asset_pk
custodianship_pk
property_statutory_record_pk
maintenance_record_pk
property_document_pk
asset_document_pk
```

---

# 4. UUID Primary Keys

The project database architecture uses UUID-based primary keys.

All Assets & Property tables shall use the approved UUID mechanism
consistently.

---

# 5. Foreign Key Standard

Foreign keys shall reference the target table's technical primary key.

Example:

```text
custodianship.property_pk
    →
property.property_pk
```

and not a business/display identifier.

---

# 6. Standard Audit Metadata

All tables shall carry the project standard audit columns:

```text
created_at                    TIMESTAMPTZ NOT NULL
created_by_sangha_sevi_pk    UUID NOT NULL
updated_at                    TIMESTAMPTZ
updated_by_sangha_sevi_pk    UUID
deleted_at                    TIMESTAMPTZ
deleted_by_sangha_sevi_pk    UUID
is_active                     BOOLEAN NOT NULL DEFAULT TRUE
```

Per AP-070.

---

# 7. Table — `property`

## 7.1 Purpose

Authoritative record of an immovable property (land, building, premises)
held by the organization.

Per AP-002.

## 7.2 Primary Key

```text
property_pk    UUID
```

## 7.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `property_pk` | Yes | Technical PK | AP-004 |
| `property_id` | Yes | Human-readable identifier (UNIQUE) | AP-005, AP-008 |
| `property_name` | Yes | Descriptive name | ERP |
| `property_type` | Yes | Classification (PENDING values) | ERD §4.5 |
| `status` | Yes | Lifecycle state | SOL-AP-003 §3 |
| `location_description` | No | Physical location (text) | AP-021, AP-022 (PENDING normalization) |
| `holding_arrangement` | No | Recorded/legal holding description | AP-009–013 (PENDING normalization) |
| `notes` | No | Additional context | ERP |
| `acquired_at` | No | Date of acquisition/registration | AP-023 |

Plus standard audit metadata (§6).

## 7.4 Status Values

Per SOL-AP-003 §3.1:

```text
REGISTERED
ACTIVE
UNDER_MAINTENANCE
DISPOSED
```

## 7.5 Holding Arrangement

Per AP-012 and AP-013, the ERP does not impose one universal
registered-owner model.

The `holding_arrangement` column captures the recorded/legal holding
information as text for initial implementation. This is architecturally
distinct from custodianship (AP-009).

The exact normalization (controlled value, structured relationship, or
other) remains PENDING per AP-013. If a future decision establishes a
more normalized model, this column will be superseded.

## 7.6 Location

Per AP-021 and AP-022, location is a property attribute distinct from
custodian and recorded holder.

`location_description` is free text for initial implementation. The exact
normalized representation remains PENDING per AP-022.

## 7.7 Property Type

Controlled values for `property_type` are not yet frozen. Candidate
values derived from source:

```text
LAND
BUILDING
PREMISES
OTHER_IMMOVABLE
```

These require explicit approval before being committed to DDL.

## 7.8 Constraints

```text
UNIQUE (property_id)
CHECK (status IN ('REGISTERED', 'ACTIVE', 'UNDER_MAINTENANCE', 'DISPOSED'))
```

---

# 8. Table — `asset`

## 8.1 Purpose

Authoritative record of a movable asset (equipment, furniture,
instruments, articles) held by the organization.

Per AP-003.

## 8.2 Primary Key

```text
asset_pk    UUID
```

## 8.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `asset_pk` | Yes | Technical PK | AP-006 |
| `asset_id` | Yes | Human-readable identifier (UNIQUE) | AP-007, AP-008 |
| `asset_name` | Yes | Descriptive name | ERP |
| `asset_type` | Yes | Classification (PENDING values) | ERD §5.4 |
| `status` | Yes | Lifecycle state | SOL-AP-003 §4 |
| `location_description` | No | Physical location/placement (text) | AP-021, AP-022 |
| `condition` | No | Current condition (text) | ERD §5.4 |
| `notes` | No | Additional context | ERP |
| `acquired_at` | No | Date of acquisition/registration | AP-023 |

Plus standard audit metadata (§6).

## 8.4 Status Values

Per SOL-AP-003 §4.1:

```text
REGISTERED
IN_CUSTODY
UNDER_MAINTENANCE
RETIRED
```

## 8.5 Asset Type

Controlled values for `asset_type` are not yet frozen. Candidate values
derived from source:

```text
EQUIPMENT
FURNITURE
INSTRUMENT
ARTICLE
OTHER_MOVABLE
```

These require explicit approval before being committed to DDL.

## 8.6 Condition

Per ERD §5.4, condition is identified as a conceptual attribute. A formal
condition grading system is NOT FROZEN (Business Rules §21). The column
is free text for initial implementation.

## 8.7 Constraints

```text
UNIQUE (asset_id)
CHECK (status IN ('REGISTERED', 'IN_CUSTODY', 'UNDER_MAINTENANCE', 'RETIRED'))
```

---

# 9. Table — `custodianship`

## 9.1 Purpose

Historical record of which organization unit has operational custody of
a property or asset.

Custodian ≠ recorded/legal holder (AP-009).

Per AP-014–020, ERD §6.

## 9.2 Primary Key

```text
custodianship_pk    UUID
```

## 9.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `custodianship_pk` | Yes | Technical PK | ERP |
| `property_pk` | Conditional | FK → property (nullable) | ERD §6.4, AP-019 |
| `asset_pk` | Conditional | FK → asset (nullable) | ERD §6.4, AP-019 |
| `custodian_organization_pk` | Yes | FK → organization | AP-015, ERD §6.4 |
| `status` | Yes | Custodianship lifecycle state | SOL-AP-003 §5 |
| `effective_from` | Yes | When custody began | ERD §6.5 |
| `effective_to` | No | When custody ended (NULL = current) | ERD §6.5 |
| `end_reason` | No | Reason custody ended | AP-058 |
| `notes` | No | Additional context | ERP |

Plus standard audit metadata (§6).

## 9.4 Status Values

Per SOL-AP-003 §5.1:

```text
ASSIGNED
ACTIVE
ENDED
```

## 9.5 End Reason

Per AP-058, dissolution/vesting must be distinguished from routine
transfer. Candidate values:

```text
TRANSFER
DISSOLUTION_VESTING
ORGANIZATIONAL_CHANGE
OTHER
```

These require explicit approval before being committed to DDL.

## 9.6 Mutual Exclusivity

Per AP-019: a custodianship record must reference EITHER a property OR
an asset (not both, not neither).

Enforcement:

```text
CHECK (
    (property_pk IS NOT NULL AND asset_pk IS NULL)
    OR
    (property_pk IS NULL AND asset_pk IS NOT NULL)
)
```

## 9.7 One Active Custodian Rule

Per AP-017: at any point in time, a property or asset shall have exactly
one active custodianship record.

This requires either:

- a partial unique index on (property_pk) WHERE status = 'ACTIVE'; or
- a partial unique index on (asset_pk) WHERE status = 'ACTIVE'; or
- application-level enforcement.

The exact mechanism shall be confirmed during DDL finalization.

## 9.8 Foreign Keys

```text
custodianship.property_pk
    → property.property_pk

custodianship.asset_pk
    → asset.asset_pk

custodianship.custodian_organization_pk
    → organization.organization_pk
```

## 9.9 History Preservation

Per AP-018: when custodianship changes, the previous record transitions
to ENDED. A new record is created. Previous records are never overwritten
or deleted.

This is enforced by the temporal model (effective_from/effective_to) and
the prohibition on physical deletion of historical custodianship records.

---

# 10. Table — `property_statutory_record`

## 10.1 Purpose

Record of statutory obligations or records associated with a property.

Per AP-034–040, ERD §7.

## 10.2 Primary Key

```text
property_statutory_record_pk    UUID
```

## 10.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `property_statutory_record_pk` | Yes | Technical PK | ERP |
| `property_pk` | Yes | FK → property | ERD §7.3, AP-040 |
| `obligation_type` | Yes | Type of statutory obligation | AP-035–038 |
| `description` | No | Additional obligation detail | ERP |
| `reference_number` | No | External statutory reference | AP-038 |
| `notes` | No | Additional context | ERP |

Plus standard audit metadata (§6).

## 10.4 Obligation Type

Source-established values per AP-035–038:

```text
LAND_REVENUE
MUNICIPAL_TAX
LAND_RECORD
OTHER
```

## 10.5 Property Only

Per AP-040: statutory records apply to immovable property only.

The `property_pk` FK is NOT NULL — every statutory record must belong
to a property. There is no `asset_pk` column.

## 10.6 Financial Consequence

Per AP-039 and FIN-ARCH-001: any payment of land revenue, municipal tax,
or other charges is a financial transaction owned by Finance.

This table does NOT contain payment amount, payment date, or transaction
columns. It identifies the obligation; Finance records the payment.

## 10.7 Foreign Keys

```text
property_statutory_record.property_pk
    → property.property_pk
```

---

# 11. Table — `maintenance_record`

## 11.1 Purpose

Historical record of maintenance activities performed on a property or
asset.

Per AP-027–033, ERD §8.

## 11.2 Primary Key

```text
maintenance_record_pk    UUID
```

## 11.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `maintenance_record_pk` | Yes | Technical PK | ERP |
| `property_pk` | Conditional | FK → property (nullable) | ERD §8.3 |
| `asset_pk` | Conditional | FK → asset (nullable) | ERD §8.3 |
| `maintenance_type` | Yes | Type of maintenance activity | AP-030 |
| `description` | No | Description of work performed | ERP |
| `performed_at` | No | Date maintenance was performed | ERP |
| `notes` | No | Additional context | ERP |

Plus standard audit metadata (§6).

## 11.4 Maintenance Type

Source-established values per AP-030:

```text
REPAIR_MINOR
REPAIR_MAJOR
IMPROVEMENT
ADDITION
ALTERATION
UPKEEP
OTHER
```

## 11.5 Mutual Exclusivity

Same pattern as custodianship: a maintenance record must reference EITHER
a property OR an asset (not both, not neither).

```text
CHECK (
    (property_pk IS NOT NULL AND asset_pk IS NULL)
    OR
    (property_pk IS NULL AND asset_pk IS NOT NULL)
)
```

## 11.6 Financial Consequence

Per AP-031 and FIN-ARCH-001: any expense resulting from maintenance
belongs to Finance.

This table does NOT contain cost, payment, or transaction columns.

## 11.7 Maintenance Scheduling

Per AP-032: the source does not establish a formal maintenance scheduling
system. This table captures what was done (historical record), not what
is planned.

## 11.8 Foreign Keys

```text
maintenance_record.property_pk
    → property.property_pk

maintenance_record.asset_pk
    → asset.asset_pk
```

---

# 12. Table — `property_document`

## 12.1 Purpose

Junction table associating properties with documents in the
Foundation-owned `document_master`.

Per AP-067–069, DOC-ARCH-001.

## 12.2 Primary Key

```text
property_document_pk    UUID
```

## 12.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `property_document_pk` | Yes | Technical PK | ERP |
| `property_pk` | Yes | FK → property | AP-069 |
| `document_master_pk` | Yes | FK → document_master (Foundation) | DOC-ARCH-001 |
| `relationship_type` | No | Nature of document relationship | ERP |
| `notes` | No | Additional context | ERP |

Plus standard audit metadata (§6).

## 12.4 Design Rationale

Per DOC-ARCH-001: no polymorphic entity FK. The explicit junction table
provides referential integrity without a generic `entity_type/entity_pk`
pattern.

## 12.5 Foreign Keys

```text
property_document.property_pk
    → property.property_pk

property_document.document_master_pk
    → document_master.document_master_pk
```

## 12.6 Uniqueness

The same document should not be associated with the same property more
than once (unless the relationship_type differs):

```text
UNIQUE (property_pk, document_master_pk)
```

If `relationship_type` is used to allow multiple associations, uniqueness
may need to include it. This shall be confirmed during DDL finalization.

---

# 13. Table — `asset_document`

## 13.1 Purpose

Junction table associating assets with documents in the Foundation-owned
`document_master`.

Per AP-067–069, DOC-ARCH-001.

## 13.2 Primary Key

```text
asset_document_pk    UUID
```

## 13.3 Logical Columns

| Column | Required | Purpose | Source |
|--------|----------|---------|--------|
| `asset_document_pk` | Yes | Technical PK | ERP |
| `asset_pk` | Yes | FK → asset | AP-069 |
| `document_master_pk` | Yes | FK → document_master (Foundation) | DOC-ARCH-001 |
| `relationship_type` | No | Nature of document relationship | ERP |
| `notes` | No | Additional context | ERP |

Plus standard audit metadata (§6).

## 13.4 Foreign Keys

```text
asset_document.asset_pk
    → asset.asset_pk

asset_document.document_master_pk
    → document_master.document_master_pk
```

## 13.5 Uniqueness

```text
UNIQUE (asset_pk, document_master_pk)
```

Same caveat as §12.6 regarding `relationship_type`.

---

# 14. Tables NOT Introduced

The following tables are explicitly NOT created by this module:

```text
property_owner / holder_master       (holding arrangement is a column, not a table — PENDING normalization)
property_location                    (location is a column — PENDING normalization)
asset_category_master                (asset_type is a controlled column value — PENDING catalogue)
property_type_master                 (property_type is a controlled column value — PENDING catalogue)
maintenance_schedule                 (scheduling not established — AP-032)
property_valuation                   (depreciation/valuation not established — AP-063)
property_insurance                   (insurance not established — §21 of AP-004)
property_inspection                  (inspection lifecycle not established)
asset_inventory                      (stock-take not established)
approval_record                      (no module-specific approval table — AP-073)
property_transaction                 (Finance owns all transactions — FIN-ARCH-001)
asset_transaction                    (Finance owns all transactions — FIN-ARCH-001)
```

---

# 15. Open Design Questions

| Question | Status | Deferred To |
|----------|--------|-------------|
| Exact property_type controlled values | PENDING | DDL phase |
| Exact asset_type controlled values | PENDING | DDL phase |
| Exact end_reason controlled values for custodianship | PENDING | DDL phase |
| Whether type masters are needed or CHECK constraints suffice | PENDING | DDL phase |
| Exact holding_arrangement normalization | PENDING (AP-013) | Future decision |
| Exact location normalization | PENDING (AP-022) | Future decision |
| relationship_type values for document junctions | PENDING | DDL phase |
| Exact property_id / asset_id format | PENDING | DDL phase |
| Sacred articles Heritage ↔ A&P cross-reference mechanism | PENDING (AP-066) | Cross-module reconciliation |

---

# 16. Cross-Module FK Summary

| This Module Table | FK Column | Target Table | Target Module |
|-------------------|-----------|-------------|---------------|
| custodianship | custodian_organization_pk | organization | Organization |
| custodianship | property_pk | property | Assets & Property (self) |
| custodianship | asset_pk | asset | Assets & Property (self) |
| property_statutory_record | property_pk | property | Assets & Property (self) |
| maintenance_record | property_pk | property | Assets & Property (self) |
| maintenance_record | asset_pk | asset | Assets & Property (self) |
| property_document | property_pk | property | Assets & Property (self) |
| property_document | document_master_pk | document_master | Foundation |
| asset_document | asset_pk | asset | Assets & Property (self) |
| asset_document | document_master_pk | document_master | Foundation |

**Inbound FK (owned by other modules):**

Finance may establish a future FK from `financial_transaction` to
`property_pk` or `asset_pk` during cross-module ERD reconciliation.
This is NOT yet frozen.

---

# 17. Indexing Recommendations

The following indexes are recommended for common access patterns:

```text
property:                  (property_id) — unique
                           (status) — filter by lifecycle state
                           (property_type) — filter by type

asset:                     (asset_id) — unique
                           (status)
                           (asset_type)

custodianship:             (property_pk, status) — find active custodian
                           (asset_pk, status)
                           (custodian_organization_pk) — find all custody by org

property_statutory_record: (property_pk) — obligations for a property

maintenance_record:        (property_pk) — maintenance history for property
                           (asset_pk) — maintenance history for asset

property_document:         (property_pk)
                           (document_master_pk)

asset_document:            (asset_pk)
                           (document_master_pk)
```

Exact index definitions shall be confirmed during DDL finalization.

---

# 18. Soft Delete

Per project convention, records use soft delete:

```text
is_active = FALSE
deleted_at = <timestamp>
deleted_by_sangha_sevi_pk = <actor>
```

Physical deletion is prohibited for:

- `custodianship` (AP-018: history preservation)
- `maintenance_record` (historical record)
- `property_statutory_record` (obligation history)

For `property` and `asset`, soft delete represents archival. Terminal
lifecycle states (DISPOSED, RETIRED) do not require soft delete — the
status column itself indicates end-of-life.

---

# 19. Delete Behavior (FK ON DELETE)

Foreign-key deletion behavior must prevent accidental destruction of
historical relationships.

Recommended approach:

```text
custodianship.property_pk                        → ON DELETE RESTRICT
custodianship.asset_pk                           → ON DELETE RESTRICT
custodianship.custodian_organization_pk          → ON DELETE RESTRICT
property_statutory_record.property_pk            → ON DELETE RESTRICT
maintenance_record.property_pk                   → ON DELETE RESTRICT
maintenance_record.asset_pk                      → ON DELETE RESTRICT
property_document.property_pk                    → ON DELETE CASCADE (junction)
property_document.document_master_pk             → ON DELETE RESTRICT
asset_document.asset_pk                          → ON DELETE CASCADE (junction)
asset_document.document_master_pk                → ON DELETE RESTRICT
```

Exact behavior shall be confirmed during DDL finalization.

---

# 20. Final Logical Schema

```text
┌─────────────────────────────────────────────────────┐
│            ASSETS & PROPERTY MODULE                  │
│                                                     │
│  property                                           │
│  asset                                              │
│  custodianship                                      │
│  property_statutory_record                          │
│  maintenance_record                                 │
│  property_document                                  │
│  asset_document                                     │
│                                                     │
│  SHARED INFRASTRUCTURE (consumed, not owned)        │
│  ─────────────────────────────────────────          │
│  organization (Organization)                        │
│  document_master (Foundation)                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

# 21. Table Count

**Module-owned tables: 7**

```text
property
asset
custodianship
property_statutory_record
maintenance_record
property_document
asset_document
```

---

# 22. Source Alignment

The table design derives from:

- SOL-AP-001 (Module Overview) — scope, boundaries, entities
- SOL-AP-002 (ERD) — entity relationships, cardinality
- SOL-AP-003 (Lifecycle) — status values, state machines
- SOL-AP-004 (Business Rules) — 74 rules, all respected

No table, column, or constraint is introduced without traceability to
an approved document or architectural principle.

---

# 23. Physical Schema Boundary

Before generating PostgreSQL DDL, the following must be finalized:

```text
Exact property_type / asset_type controlled values
Exact holding_arrangement representation
Exact location representation
Exact property_id / asset_id format
Exact end_reason values
Exact document relationship_type values
Exact data types (VARCHAR lengths, etc.)
Exact index definitions
Exact ON DELETE behavior
Whether type masters vs CHECK constraints
Cross-module FK from Finance (if any)
Heritage cross-reference mechanism
```

---

# 24. Database-First Principle

The Assets & Property implementation shall follow:

```text
Business Rules
      ↓
ERD
      ↓
Table Design
      ↓
PostgreSQL DDL
      ↓
ORM
      ↓
API
      ↓
UI
      ↓
Testing
      ↓
Release
```

No SQL shall be generated from undocumented assumptions.

---

# 25. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```
