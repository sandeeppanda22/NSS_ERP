# NSS ERP — Assets & Property ERD

**Document ID:** SOL-AP-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Assets & Property
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the Entity-Relationship model for Module #22 —
Assets & Property.

It establishes the primary entities, supporting relationship entities,
cross-module references, and cardinality rules derived from the source
material.

---

# 2. Architectural Decisions Applied

| Decision | Source |
|----------|--------|
| Property and Asset are separate entities | ERD Decision #1 |
| Custodianship is a separate historical relationship entity | ERD Decision #2 |
| Recorded/legal holding arrangement is distinct from custodianship | ERD Decision #3 |
| Exact legal-holder normalization deferred to Business Rules | ERD Decision #3 |
| Statutory records are a separate entity | ERD Decision #4 |
| Maintenance records are a separate entity | ERD Decision #5 |
| Finance owns all financial transactions (FIN-ARCH-001) | ARCH-CROSS-001 §5 |
| Foundation owns document_master (DOC-ARCH-001) | ARCH-CROSS-001 §6 |
| One-owner-per-table (ARCH-001) | ARCH-CROSS-001 §3 |

---

# 3. Entity Classification

## 3.1 Primary Entities

| Entity | Domain Concept |
|--------|---------------|
| Property | Immovable property (land, buildings, premises) |
| Asset | Movable property (equipment, furniture, instruments, articles) |

## 3.2 Supporting / Relationship Entities

| Entity | Domain Concept |
|--------|---------------|
| Custodianship | Historical record of which organization unit has operational custody |
| Statutory Record | Property-level statutory obligations and records |
| Maintenance Record | Historical record of maintenance activities |

## 3.3 Cross-Module References (NOT owned by Assets & Property)

| Entity | Owner |
|--------|-------|
| organization | Organization module |
| document_master | Foundation module |
| financial_transaction | Finance module |

---

# 4. Primary Entity — Property

## 4.1 Definition

An immovable property record representing land, buildings, or premises
held by the organization.

## 4.2 Source Basis

- Nilachala Kutir, Swargadwar, Puri
- Smruti Mandir, Puri
- Sikshya Kendra, Biratung, P.S-Gop, Dist-Puri
- Other landed properties (Bye-Law Section F)
- Buildings referenced in Mahila Bye-Law (Kutir provisions)

## 4.3 Identity

```text
property_pk        (UUID, technical primary key)
property_id        (human-readable identifier — format TBD)
```

## 4.4 Recorded/Legal Holding Arrangement

The property record shall capture the recorded/legal holding arrangement.

This is architecturally distinct from custodianship.

Source-established arrangements:

- Kendra properties: recorded in the name of Shri Shri Thakur under
  maarfatdarship of Kendra Sangha
- Mahila properties: landed properties held in the name of the President

The exact normalized representation (text, controlled value, or
relationship) remains a Business Rules / Table Design decision.

## 4.5 Key Attributes (Conceptual)

The following attribute domains are identified from the source:

```text
Identity
Location / Address
Recorded/legal holding arrangement
Property type/classification
Status
```

Exact columns are NOT frozen by this ERD. They belong in Table Design.

---

# 5. Primary Entity — Asset

## 5.1 Definition

A movable property/asset record representing equipment, furniture,
instruments, articles, or other movable property held by the organization.

## 5.2 Source Basis

- "all movable and immovable properties" (Bye-Law)
- "articles used by Shri Shri Thakur and associated with his memory"
  (Bye-Law item 8)
- Movable property referenced in Mahila Bye-Law

## 5.3 Identity

```text
asset_pk           (UUID, technical primary key)
asset_id           (human-readable identifier — format TBD)
```

## 5.4 Key Attributes (Conceptual)

```text
Identity
Asset type/classification
Location / Placement
Condition
Status
```

Exact columns are NOT frozen by this ERD. They belong in Table Design.

---

# 6. Supporting Entity — Custodianship

## 6.1 Definition

A historical record of which organization unit has operational custody
of a property or asset.

Custodian ≠ recorded/legal holder.

## 6.2 Source Basis

- "custodian of all the properties, movable and immovable" (Bye-Law §C)
- "Office-bearers of these Sakha Sanghas will function as the custodians"
  (Bye-Law item 12)
- Mahila dissolution: "remaining property vests in Kendra Sangha"
  (implies custodianship change)

## 6.3 Historical Nature

Custodianship is modeled as a separate entity (not merely a column on
property/asset) because:

- custodians can change over time;
- source establishes transfer scenarios (dissolution, organizational
  change);
- historical custody must remain interpretable.

## 6.4 Relationships

```text
custodianship
    │
    ├── property_pk (FK → property) — nullable
    │
    ├── asset_pk (FK → asset) — nullable
    │
    └── custodian_organization_pk (FK → organization)
```

A custodianship record references EITHER a property OR an asset (not both).

The exact enforcement mechanism (check constraint, separate tables, or
other) belongs in Table Design.

## 6.5 Temporal Concept

A custodianship record captures:

```text
Effective from (when custody began)
Effective to (when custody ended — NULL if current)
```

This allows historical tracking without overwriting.

---

# 7. Supporting Entity — Statutory Record

## 7.1 Definition

A record of statutory obligations or records associated with a property.

## 7.2 Source Basis

- "payment of land revenue" (Bye-Law item 4)
- "municipal tax and other charges" (Mahila Bye-Law §g)
- "proper maintenance of land records in the name of Shri Shri Thakur"
  (Mahila Bye-Law §g)

## 7.3 Relationship

```text
property
    │ 1:N
    ▼
statutory_record
```

A property may have multiple statutory obligations.

Statutory records belong to immovable property only (land revenue,
municipal tax, land records are not applicable to movable assets).

## 7.4 Financial Consequence

A statutory obligation may result in a financial transaction (e.g., tax
payment). Per FIN-ARCH-001, that transaction belongs to Finance:

```text
statutory_record
    │
    │ business context
    ▼
Finance.financial_transaction
```

The statutory_record provides the business reason. Finance owns the
payment.

---

# 8. Supporting Entity — Maintenance Record

## 8.1 Definition

A historical record of maintenance activities performed on a property
or asset.

## 8.2 Source Basis

- "proper maintenance and necessary improvements" (Bye-Law item 4)
- "annual repair works both minor and major" (Mahila Bye-Law §g)
- "necessary additions and alterations to the buildings" (Mahila Bye-Law §g)
- "proper upkeep and maintenance of the articles" (Bye-Law item 8)

## 8.3 Relationship

```text
property / asset
    │ 1:N
    ▼
maintenance_record
```

Maintenance records apply to both property and asset.

The exact modeling (one table with property/asset FK, or two separate
tables) belongs in Table Design.

## 8.4 Financial Consequence

A maintenance activity may result in a financial transaction (expense).
Per FIN-ARCH-001, that transaction belongs to Finance.

---

# 9. Conceptual ERD Diagram

```text
┌───────────────────────────────────────────────────────────────────┐
│                     ASSETS & PROPERTY MODULE                      │
│                                                                   │
│  ┌──────────────┐                    ┌──────────────┐            │
│  │   PROPERTY   │                    │    ASSET     │            │
│  │  (immovable) │                    │  (movable)   │            │
│  └──────┬───────┘                    └──────┬───────┘            │
│         │                                   │                    │
│         │         ┌───────────────┐         │                    │
│         ├────────→│ CUSTODIANSHIP │←────────┤                    │
│         │         └───────┬───────┘         │                    │
│         │                 │                 │                    │
│         │                 │                 │                    │
│         │         ┌───────┴───────┐         │                    │
│         │         │  ORGANIZATION │         │                    │
│         │         │   (external)  │         │                    │
│         │         └───────────────┘         │                    │
│         │                                   │                    │
│         ├────────→ STATUTORY_RECORD          │                    │
│         │         (property only)            │                    │
│         │                                   │                    │
│         ├────────→ MAINTENANCE_RECORD ←─────┤                    │
│         │                                   │                    │
│         └────────→ DOCUMENT_MASTER ←────────┘                    │
│                   (Foundation, external)                          │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘

Cross-module financial consequence (NOT owned):

    STATUTORY_RECORD ─────┐
                          │ business context
    MAINTENANCE_RECORD ───┼──────────→ Finance.financial_transaction
                          │
    PROPERTY / ASSET ─────┘
    (acquisition/disposal)
```

---

# 10. Cardinality Summary

| Relationship | Cardinality | Notes |
|---|---|---|
| Property → Custodianship | 1:N | Historical; one current per property |
| Asset → Custodianship | 1:N | Historical; one current per asset |
| Custodianship → Organization | N:1 | Custodian is always an organization unit |
| Property → Statutory Record | 1:N | Multiple obligations per property |
| Property → Maintenance Record | 1:N | Multiple events over time |
| Asset → Maintenance Record | 1:N | Multiple events over time |
| Property → Document Master | M:N | Multiple documents per property |
| Asset → Document Master | M:N | Multiple documents per asset |

---

# 11. Cross-Module Relationships

## 11.1 Organization (consumed)

```text
custodianship.custodian_organization_pk
    → organization.organization_pk
```

Assets & Property does not own or modify Organization records.

## 11.2 Foundation — Document Master (consumed)

Property and Asset may reference documents through the Foundation-owned
common document registry.

The exact association mechanism (junction table or direct FK) belongs in
Table Design, respecting DOC-ARCH-001 (no polymorphic entity FK).

## 11.3 Finance (referenced, never owned)

Financial transactions resulting from property/asset activities are owned
by Finance per FIN-ARCH-001.

The existence and form of any FK from Finance back to Assets & Property
will be determined during cross-module ERD reconciliation.

---

# 12. What This ERD Does NOT Define

```text
Exact columns / data types
Exact FK column names
Exact constraints
Exact indexes
Junction table structures
Finance entity details
Organization entity details
Foundation entity details
Audit metadata columns
```

These belong in Business Rules (04) and Table Design (05).

---

# 13. Open Questions for Business Rules

| Question | Deferred To |
|----------|-------------|
| Exact property type classification values | Business Rules |
| Exact asset type classification values | Business Rules |
| Exact representation of recorded/legal holder | Business Rules |
| Whether maintenance applies differently to property vs asset | Business Rules |
| Whether a single maintenance_record table or two | Table Design |
| Document association mechanism | Table Design |
| Custodianship enforcement (check constraint vs separate tables) | Table Design |

---

# 14. Tables Implied by This ERD

| # | Candidate Table | Primary Entity | Notes |
|---|---|---|---|
| 1 | property | Yes | Immovable property |
| 2 | asset | Yes | Movable asset |
| 3 | custodianship | Supporting | Historical custody record |
| 4 | property_statutory_record | Supporting | Property statutory obligations |
| 5 | maintenance_record | Supporting | Maintenance history |

Additional tables may emerge from Business Rules (e.g., type masters,
document junction tables). These 5 are the minimum source-derived set.

---

# 15. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```
