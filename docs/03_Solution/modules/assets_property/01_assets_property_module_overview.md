# NSS ERP — Assets & Property Module Overview

**Document ID:** SOL-AP-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Assets & Property
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This module manages the identification, registration, custody, maintenance,
and lifecycle of NSS movable and immovable property and assets.

It provides the authoritative physical/administrative record of what the
organization owns, holds in custody, or is responsible for maintaining.

Assets & Property owns the physical/administrative property and asset record.
It does not determine the legal/statutory authority under which property is
held, which remains governed by the applicable Bye-Law and Governance
arrangements.

---

# 2. Source Authority

The following Bye-Law provisions establish the Assets & Property domain:

**NSS Bye-Law:**

- Kendra Sangha is custodian of all properties, movable and immovable,
  pertaining to Nilachala Kutir and Smruti Mandir at Puri and the Sikshya
  Kendra at Biratung (recorded in the name of Shri Shri Thakur under
  maarfatdarship of Kendra Sangha).
- Maintenance and necessary improvements of Nilachala Kutir including all
  other movable and immovable properties; arrangement for payment of land
  revenue and other taxes.
- Income from all immovable properties of the Kendra Sangha (Section F).

**NSS Mahila Sangha Bye-Law:**

- Governing Body is competent to hold and acquire properties and dispose
  of them in furtherance of the aims and objects of the Sangha.
- Landed properties held in the name of the President.
- Earnings from landed properties and other sources.
- On dissolution, remaining property vests in Kendra Sangha.
- Annual repair works, additions and alterations to buildings, payment of
  land revenue, municipal tax, and maintenance of land records.

---

# 3. Scope

## 3.1 In Scope

- Immovable property (land, buildings, premises)
- Movable assets (equipment, furniture, instruments, articles)
- Property/asset identity and registration
- Custodianship (which organization unit has operational responsibility)
- Recorded/legal holding information
- Location/placement
- Acquisition record
- Maintenance record
- Condition tracking
- Transfer/relocation
- Disposal/retirement
- Property-related statutory records (land revenue, municipal records)

## 3.2 Out of Scope

The following are NOT owned by Assets & Property:

| Concern | Owner |
|---------|-------|
| All financial transactions (purchase, income, tax payments) | Finance |
| Depreciation / accounting treatment | Finance |
| Governing-body authority for acquisition/disposal | Governance |
| Historical/cultural significance | Heritage |
| Organizational hierarchy | Organization |

**FIN-ARCH-001 — Financial Transaction Ownership:**

All financial transactions arising from or associated with property/assets
are owned by Finance. Assets & Property does not create, own, or duplicate
financial transaction records. Any module may originate, classify, reference,
or provide business context for a financial transaction, but no non-Finance
module shall create or own a duplicate financial transaction table.

---

# 4. Module Boundary

## 4.1 Ownership Principle

Assets & Property owns the **physical/administrative identity and lifecycle**
of property and assets.

Other modules interact with this domain but do not duplicate its records:

```
Assets & Property
├── Property identity
├── Asset identity
├── Recorded/legal holding information
├── Custody
├── Maintenance
├── Condition
├── Acquisition/disposal record
└── Statutory records

Finance
├── Purchase transactions
├── Property income
├── Tax/revenue payments
└── Depreciation (future)

Governance
├── Acquisition/disposal authority
└── Governing-body decisions

Heritage
└── Historical/cultural interpretation
```

## 4.2 Cross-Module References

| External Module | Relationship |
|----------------|-------------|
| Organization | Custodian organization (FK to `organization`) |
| Finance | Financial transactions related to property (Finance owns) |
| Governance | Authority decisions (Governance owns) |
| Heritage | Cultural significance records (Heritage owns) |
| Foundation | Document registry for property documents |

## 4.3 Financial Transaction Boundary

Assets & Property provides the property/asset business context. Finance
records all resulting financial transactions. Any cross-reference between
the two modules shall be determined during ERD/DDL reconciliation.

```
Assets & Property
    property/asset record (business context)
        │
        │ reference
        ▼
Finance
    financial transaction (Finance owns)
```

Finance already has `PROPERTY_INCOME` as a classification code. Additional
property-related classifications and any FK from Finance to Assets & Property
will be determined during cross-module ERD reconciliation.

---

# 5. Domain Entities

## 5.1 Property vs. Asset

This module covers two related but distinct domain concepts:

```
PROPERTY (Immovable)
────────────────────
Land
Buildings
Other immovable holdings

ASSET (Movable)
───────────────
Equipment
Furniture
Instruments
Other movable property
```

Whether these become one table or separate tables is NOT decided here.
That belongs in the ERD.

Land/buildings have materially different attributes from movable assets
(statutory records, land revenue, municipal tax vs. maintenance/condition
tracking). The ERD must account for this difference.

## 5.2 Source-Established Property

Physical land and buildings established by the source:

- Nilachala Kutir, Swargadwar, Puri
- Smruti Mandir, Puri
- Sikshya Kendra, Biratung, P.S-Gop, Dist-Puri
- Other landed properties (per Bye-Law Section F)

## 5.3 Source-Established Asset Categories

The source establishes the concept of "movable property" without enumerating
specific categories.

Candidate asset/property categories beyond those directly established by the
source shall be determined during Business Rules and ERD review.

## 5.4 Entity Decision

Property and Asset are **separate primary entities** (ERD Decision #1,
SOL-AP-002). They share supporting entities (custodianship, maintenance)
but are distinct in identity, attributes, and statutory applicability.

---

# 6. Recorded/Legal Holding and Custodianship

## 6.1 Holding Arrangements

The Bye-Law establishes different holding arrangements for different
organizational contexts:

- **Kendra properties:** Recorded in the name of Shri Shri Thakur under
  maarfatdarship of Kendra Sangha.
- **Mahila properties:** Landed properties held in the name of the
  President.

Recorded/legal holding information shall be captured according to the
applicable statutory/legal arrangement. The ERP does not freeze one
universal registered-owner rule.

## 6.2 Three-Part Property Relationship

```
Property
   │
   ├── Recorded/legal holder (varies by arrangement)
   │
   ├── Custodian organization (operational responsibility)
   │
   └── Physical location
```

The exact representation of "recorded/legal holder" shall be determined
during the ERD, as the Bye-Law terminology differs between Kendra and
Mahila provisions.

---

# 7. Lifecycle Concepts

Based on the source material, the following lifecycle states are established
(finalized in SOL-AP-003):

```
Property:  REGISTERED → ACTIVE ↔ UNDER_MAINTENANCE → DISPOSED

Asset:     REGISTERED → IN_CUSTODY ↔ UNDER_MAINTENANCE → RETIRED
```

Transfer/relocation is handled through custodianship and location history,
not as a lifecycle state. UNDER_MAINTENANCE is temporary — the entity
returns to its active state after maintenance completes.

---

# 8. Statutory Requirements

The Bye-Law identifies specific statutory/administrative responsibilities:

- Payment of land revenue
- Payment of municipal tax
- Maintenance of land records
- Proper maintenance and necessary improvements

These imply the ERP should support:

- Recording of statutory obligations per property
- Tracking of payments (via Finance cross-reference)
- Maintenance recording

---

# 9. Mahila Property

The Mahila Bye-Law establishes:

- Governing Body competence to hold/acquire/dispose property
- Landed properties held in President's name
- On dissolution, remaining property vests in Kendra Sangha, subject to
  the applicable statutory arrangement

The ERP handles this through:

- Assets & Property records the property
- Custodian = Mahila Sangha organization unit
- Authority for acquisition/disposal = Governance (Mahila Governing Body)
- Dissolution provisions to be represented in the Lifecycle/Business Rules
  documents

---

# 10. Relationship to Heritage

Heritage records the historical/cultural significance of locations and
objects. Assets & Property records the administrative/operational reality.

Both may reference the same physical entity (e.g., Nilachala Kutir) but
from different perspectives:

```
Heritage
    nss_historical_milestone (cultural event at Kutir)
    founder_master (historical connection)

Assets & Property
    property (administrative record, custody, maintenance)
```

No duplicate records. Cross-reference by FK where needed.

---

# 11. Tables Not Yet Defined

This Overview does not freeze any physical tables.

Table design follows:

```
Overview
    ↓
ERD
    ↓
Lifecycle
    ↓
Business Rules
    ↓
Table Design
```

---

# 12. Implementation Tier

**Candidate dependency:** Foundation and Organization.

Finance/Governance/Heritage relationships will be reconciled during the
final dependency-graph phase.

Tier position remains OPEN until that review.

---

# 13. Open Questions

| Question | Status |
|----------|--------|
| Exact property categories (land/building/equipment/etc.) | PENDING — derive from source |
| Whether rented premises are tracked | PENDING |
| Maintenance scheduling vs. maintenance record-only | PENDING |
| Asset valuation (book value, current value) | PENDING — Finance deferred depreciation |
| ~~One table vs. separate tables for property/asset~~ | **RESOLVED — ERD Decision #1: separate entities** |
| Exact representation of recorded/legal holder | PENDING — Table Design decision |

---

# 14. What This Module Does NOT Do

```
Duplicate Organization hierarchy
Duplicate Finance transactions
Create a full accounting/depreciation system
Replace Heritage historical records
Introduce governance/approval tables
Determine legal/statutory authority for property holding
Invent requirements not supported by source
```

---

# 15. Architectural Decisions Frozen

## ASSET-ARCH-001 — Module Acceptance

Assets & Property is accepted as Module #22 of NSS ERP.

## FIN-ARCH-001 — Financial Transaction Ownership (Project-Wide)

Finance is the sole owner of financial transactions within NSS ERP. Any
module may originate, classify, reference, or provide business context for
a financial transaction, but no non-Finance module shall create or own a
duplicate financial transaction table.

---

# 16. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```
