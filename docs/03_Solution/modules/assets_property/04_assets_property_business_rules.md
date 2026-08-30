# NSS ERP — Assets & Property Business Rules

**Document ID:** SOL-AP-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Assets & Property
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules for Module #22 — Assets & Property.

Each rule is classified by source authority and tagged with a unique
identifier (AP-nnn).

---

# 2. Rule Classification

| Classification | Meaning |
|---------------|---------|
| CONSTITUTIONAL | Directly derived from NSS Bye-Law or Mahila Bye-Law |
| ERP | Architectural decision made during ERP documentation phase |
| CROSS-MODULE | Rule that enforces a project-wide principle (ARCH-CROSS-001) |
| PENDING | Identified requirement where the source does not yet provide enough detail to freeze |

---

# 3. Property vs Asset Distinction

## AP-001 — Separate Property and Asset Entities (ERP)

Property (immovable) and Asset (movable) are separate primary entities
within the Assets & Property module.

**Rationale:** Land/buildings have fundamentally different characteristics
(statutory records, land revenue, municipal obligations, area) compared
to movable assets (condition, placement, maintenance cycles).

## AP-002 — Property Definition (CONSTITUTIONAL)

Property represents immovable holdings: land, buildings, and premises.

**Source:** Bye-Law: "all properties, movable and immovable, pertaining to
Nilachala Kutir and Smruti Mandir at Puri and the Sikshya Kendra at
Biratung"; Mahila Bye-Law: "landed properties".

## AP-003 — Asset Definition (CONSTITUTIONAL)

Asset represents movable property: equipment, furniture, instruments,
articles, and other movable items.

**Source:** Bye-Law: "movable and immovable properties"; item 8: "articles
used by Shri Shri Thakur and associated with his memory".

---

# 4. Property and Asset Identity

## AP-004 — Property Technical Identity (ERP)

Every property record shall have a UUID primary key (`property_pk`)
following the project database standard.

## AP-005 — Property Human-Readable Identity (ERP)

Every property record shall have a human-readable identifier
(`property_id`). The exact format is subject to Table Design.

## AP-006 — Asset Technical Identity (ERP)

Every asset record shall have a UUID primary key (`asset_pk`) following
the project database standard.

## AP-007 — Asset Human-Readable Identity (ERP)

Every asset record shall have a human-readable identifier (`asset_id`).
The exact format is subject to Table Design.

## AP-008 — Identity Uniqueness (ERP)

Both `property_id` and `asset_id` shall be unique within their respective
entities. A property identifier shall never collide with an asset
identifier by design (distinct namespaces or prefixes).

---

# 5. Recorded/Legal Holding Arrangement

## AP-009 — Holding Arrangement Is Distinct from Custodianship (ERP)

The recorded/legal holding arrangement represents in whose name the
property is legally recorded. This is architecturally distinct from
operational custodianship.

## AP-010 — Kendra Property Holding (CONSTITUTIONAL)

Properties pertaining to Nilachala Kutir, Smruti Mandir at Puri, and
Sikshya Kendra at Biratung are recorded in the name of Shri Shri Thakur
under the maarfatdarship of Kendra Sangha in all revenue, municipal, and
other concerned records.

**Source:** Bye-Law §C(2)(i).

## AP-011 — Mahila Property Holding (CONSTITUTIONAL)

Landed properties of the Mahila Sangha are held in the name of the
President.

**Source:** Mahila Bye-Law, Funds section item (g).

## AP-012 — No Universal Holding Rule (ERP)

The ERP shall not impose one universal registered-owner model. Different
organizational contexts may have different holding arrangements as
established by their respective statutory provisions.

## AP-013 — Holding Arrangement Normalization (PENDING)

The exact normalized representation of the holding arrangement (text
field, controlled value, structured relationship, or combination) is not
yet frozen. It requires further analysis of all holding scenarios during
Table Design.

---

# 6. Custodianship

## AP-014 — Custodian Definition (CONSTITUTIONAL)

The custodian is the organization unit with operational responsibility
for maintaining and managing the property or asset.

**Source:** Bye-Law §C(2)(i): Kendra Sangha is "custodian of all the
properties"; Bye-Law item 12: "Office-bearers of these Sakha Sanghas will
function as the custodians".

## AP-015 — Custodian Is Always an Organization (ERP)

The custodian shall always be an organization unit (FK to
`organization.organization_pk`). Custodianship is not assigned to
individuals.

## AP-016 — Custodianship as Separate Entity (ERP)

Custodianship is modeled as a separate entity to support historical
tracking. It is not merely a column on the property/asset record.

## AP-017 — One Active Custodian Per Property/Asset (ERP)

At any point in time, a property or asset shall have exactly one active
custodianship record.

## AP-018 — Custodianship History Preservation (ERP)

When custodianship changes, the previous custodianship record transitions
to ENDED. A new custodianship record is created. Previous records are
never overwritten or deleted.

## AP-019 — Custodianship Requires Property or Asset (ERP)

A custodianship record must reference either a property or an asset (not
both, not neither).

## AP-020 — Sakha Custodianship (CONSTITUTIONAL)

Office-bearers of Sakha Sanghas function as custodians of the properties
and other assets given to their charge.

**Source:** Bye-Law item 12.

---

# 7. Physical Location

## AP-021 — Location Is a Property/Asset Attribute (ERP)

Physical location/placement is captured on the property or asset record
itself.

Location is distinct from:

- recorded/legal holding arrangement;
- custodian organization.

## AP-022 — Location Representation (PENDING)

The exact representation of location (free text, structured address,
FK to a location entity, or combination) is not yet frozen. It requires
Table Design analysis.

---

# 8. Acquisition

## AP-023 — Acquisition Record (ERP)

The ERP shall record when and how a property or asset was acquired
(registered into the system).

## AP-024 — Acquisition Authority (CONSTITUTIONAL)

The Governing Body is competent to acquire properties in furtherance of
the aims and objects of the Sangha.

**Source:** Mahila Bye-Law: "Governing Body shall be competent to hold and
acquire properties and dispose of them in furtherance of the aims and
objects of the Sangha."

## AP-025 — Acquisition Authority Belongs to Governance (CROSS-MODULE)

The authority/approval for acquisition is a Governance module concern.
Assets & Property records the acquisition event; it does not manage the
approval process.

## AP-026 — Acquisition Financial Transaction (CROSS-MODULE)

Any purchase or payment transaction resulting from an acquisition belongs
to Finance per FIN-ARCH-001. Assets & Property records the acquisition
context only.

---

# 9. Maintenance and Improvements

## AP-027 — Maintenance Responsibility (CONSTITUTIONAL)

Kendra Sangha is responsible for proper maintenance and necessary
improvements of Nilachala Kutir including all other movable and immovable
properties.

**Source:** Bye-Law item 4.

## AP-028 — Mahila Maintenance Responsibility (CONSTITUTIONAL)

Annual repair works both minor and major, necessary additions and
alterations to buildings of the Kutir, along with proper maintenance of
land records, shall always be done by Nilachala Saraswata Sangha.

**Source:** Mahila Bye-Law §g.

## AP-029 — Maintenance as Historical Record (ERP)

Maintenance activities are recorded as historical events
(maintenance_record). The record captures what was done, not a future
schedule.

## AP-030 — Maintenance Types (CONSTITUTIONAL)

Source-established maintenance types:

- Repairs (minor and major)
- Improvements
- Additions
- Alterations
- Upkeep of articles

**Source:** Bye-Law item 4; Mahila Bye-Law §g; Bye-Law item 8.

## AP-031 — Maintenance Does Not Create Financial Transactions (CROSS-MODULE)

A maintenance_record records the maintenance event. Any resulting expense
or payment is a Finance module transaction per FIN-ARCH-001.

## AP-032 — Maintenance Scheduling Not Established (PENDING)

The source does not establish a formal maintenance scheduling system.
Recurring maintenance scheduling is not frozen. If needed in the future,
it requires a separate business rule.

## AP-033 — Article Maintenance (CONSTITUTIONAL)

Proper upkeep and maintenance of the articles used by Shri Shri Thakur
and associated with his memory is a specific responsibility.

**Source:** Bye-Law item 8.

---

# 10. Statutory Property Records

## AP-034 — Statutory Obligations Are Separate Records (ERP)

A property may have multiple statutory obligations. These are captured as
separate records (property_statutory_record), not as columns on the
property record.

## AP-035 — Land Revenue Obligation (CONSTITUTIONAL)

Payment of land revenue is a statutory obligation for applicable
properties.

**Source:** Bye-Law item 4: "arrange payment of land revenue"; Mahila
Bye-Law §g: "payment of land revenue".

## AP-036 — Municipal Tax Obligation (CONSTITUTIONAL)

Payment of municipal tax is a statutory obligation for applicable
properties.

**Source:** Mahila Bye-Law §g: "municipal tax and other charges".

## AP-037 — Land Record Maintenance (CONSTITUTIONAL)

Proper maintenance of land records in the name of Shri Shri Thakur is a
statutory/administrative responsibility.

**Source:** Mahila Bye-Law §g: "proper maintenance of land records in the
name of Shri Shri Thakur".

## AP-038 — Revenue/Municipal Records (CONSTITUTIONAL)

Properties shall be recorded in all revenue, municipal, and other
concerned records as required by the holding arrangement.

**Source:** Bye-Law §C(2)(i): "recorded in the name of Shri Shri Thakur
under the maarfatdarship of Kendra Sangha in all revenue municipal and
other concerned records."

## AP-039 — Statutory Payment Is Finance-Owned (CROSS-MODULE)

Any payment of land revenue, municipal tax, or other charges is a
financial transaction owned by Finance per FIN-ARCH-001. The
property_statutory_record provides business context only.

## AP-040 — Statutory Records Apply to Property Only (ERP)

Statutory records (land revenue, municipal tax, land records) apply to
immovable property. They do not apply to movable assets.

---

# 11. Transfer of Custodianship

## AP-041 — Transfer Is Not a Property State (ERP)

When custodianship transfers, the property/asset remains in its current
lifecycle state (ACTIVE or IN_CUSTODY). The custodianship record changes;
the property/asset state does not.

## AP-042 — Transfer Creates New Custodianship (ERP)

A transfer results in:

1. Current custodianship record → ENDED
2. New custodianship record → ASSIGNED → ACTIVE

Both records are preserved for historical completeness.

## AP-043 — Transfer May Include Location Change (ERP)

A custodianship transfer may or may not involve a physical relocation.
Location change and custodianship change are independent operations that
may coincide.

---

# 12. Disposal and Retirement

## AP-044 — Disposal Authority (CONSTITUTIONAL)

The Governing Body is competent to dispose of properties in furtherance
of the aims and objects of the Sangha.

**Source:** Mahila Bye-Law: "dispose of them in furtherance of the aims and
objects of the Sangha."

## AP-045 — Disposal Authority Belongs to Governance (CROSS-MODULE)

The authority/approval for disposal is a Governance module concern.
Assets & Property records the disposal event; it does not manage the
approval process.

## AP-046 — Disposal Is Terminal (ERP)

A disposed property cannot return to ACTIVE status.

## AP-047 — Retirement Is Terminal (ERP)

A retired asset cannot return to IN_CUSTODY status.

## AP-048 — Disposal Financial Consequence (CROSS-MODULE)

Any proceeds or write-off from disposal is a Finance module transaction
per FIN-ARCH-001.

---

# 13. Kendra-Specific Property Rules

## AP-049 — Kendra Custodianship (CONSTITUTIONAL)

Kendra Sangha is the custodian of all properties, movable and immovable,
pertaining to Nilachala Kutir, Smruti Mandir at Puri, and Sikshya Kendra
at Biratung.

**Source:** Bye-Law §C(2)(i).

## AP-050 — Kendra Property Management Authority (CONSTITUTIONAL)

The Governing Body may appoint a paid Manager and other staff for proper
management of all properties of the Kendra Sangha.

**Source:** Bye-Law §C(2)(ix).

## AP-051 — Kendra Property Rules and Regulations (CONSTITUTIONAL)

The Governing Body shall frame rules and regulations for proper management
and maintenance of all properties mentioned in Bye-Law §C(2)(i).

**Source:** Bye-Law §C(2)(xiv).

## AP-052 — Kendra Seva Puja Properties (CONSTITUTIONAL)

The articles, instruments, and premises used for day-to-day seva pujas
at Nilachala Kutir, Smruti Mandir, and Sikshya Kendra are Kendra
properties requiring maintenance.

**Source:** Bye-Law items 2, 5, 6.

---

# 14. Mahila Property Rules

## AP-053 — Mahila Property Competence (CONSTITUTIONAL)

The Mahila Sangha Governing Body is competent to hold, acquire, and
dispose of properties in furtherance of the aims and objects of the
Sangha.

**Source:** Mahila Bye-Law (Property clause).

## AP-054 — Mahila Landed Properties (CONSTITUTIONAL)

Landed properties of the Mahila Sangha are held in the name of the
President.

**Source:** Mahila Bye-Law, Funds section item (g).

## AP-055 — Mahila Earnings from Property (CONSTITUTIONAL)

Earnings from landed properties are a source of Mahila Sangha funds.

**Source:** Mahila Bye-Law, Funds section item (f): "Earnings from landed
properties and other sources, if any."

## AP-056 — Mahila Kutir Maintenance by Kendra (CONSTITUTIONAL)

Regardless of Mahila Sangha property provisions, the annual repair works,
additions and alterations to the buildings of the Kutir, payment of land
revenue, municipal tax, and maintenance of land records in the name of
Shri Shri Thakur shall always be done by Nilachala Saraswata Sangha
(Kendra).

**Source:** Mahila Bye-Law §g.

---

# 15. Dissolution and Vesting

## AP-057 — Mahila Dissolution Vesting (CONSTITUTIONAL)

On dissolution of the Mahila Sangha, remaining property vests in Kendra
Sangha, subject to the applicable statutory arrangement.

**Source:** Mahila Bye-Law §12 (Dissolution).

## AP-058 — Dissolution Is Not Routine Transfer (ERP)

Dissolution/vesting is a statutory consequence distinct from a routine
custodianship transfer. The ERP representation must distinguish between:

- routine transfer (operational decision by authorized body);
- statutory vesting (triggered by dissolution provisions).

The exact representation (custodianship end-reason, separate event type,
or other mechanism) belongs in Table Design.

## AP-059 — Vesting Preserves History (ERP)

When property vests in Kendra Sangha upon dissolution, the historical
custodianship under the previous organization is preserved. The record
shows:

1. Previous custodianship: ENDED (reason: dissolution/vesting)
2. New custodianship: Kendra Sangha

---

# 16. Finance Boundary

## AP-060 — No Financial Transaction Tables (CROSS-MODULE)

Assets & Property shall not create, own, or duplicate any financial
transaction table. Per FIN-ARCH-001, Finance is the sole owner of
financial transactions.

## AP-061 — Business Context Only (CROSS-MODULE)

Assets & Property provides the property/asset business context for
financial events. The financial transaction itself is recorded and owned
by Finance.

## AP-062 — Property Income Is Finance-Owned (CROSS-MODULE)

Income from immovable properties is recorded as a Finance module
transaction. Assets & Property identifies which property generates
income; Finance records the transaction.

**Source for the income concept:** Bye-Law Section F item (viii): "Income
from all immovable properties of the Kendra Sangha."

## AP-063 — No Depreciation or Valuation (PENDING)

The source does not establish an asset depreciation, book-value, or
current-value model. These are not frozen. If required in the future,
they shall be governed by Finance module rules.

---

# 17. Heritage Boundary

## AP-064 — Heritage Does Not Own Property Records (CROSS-MODULE)

Heritage records historical/cultural significance. Assets & Property
records administrative/operational reality. Both may reference the same
physical entity from different perspectives.

## AP-065 — No Duplicate Entity (CROSS-MODULE)

A physical location or article shall not be duplicated across Heritage
and Assets & Property. Cross-reference by FK where both modules need to
relate to the same entity.

## AP-066 — Sacred Articles Boundary (PENDING)

The boundary between "articles associated with Shri Shri Thakur's memory"
(Heritage significance) and "articles requiring operational maintenance"
(Assets & Property) is not fully defined. Both modules may reference the
same physical article. The exact cross-reference mechanism belongs in
cross-module ERD reconciliation.

---

# 18. Document Boundary

## AP-067 — Documents Are Foundation-Owned (CROSS-MODULE)

Property and asset documents (title deeds, land records, maintenance
certificates, photographs, etc.) use the Foundation-owned
`document_master` per DOC-ARCH-001.

## AP-068 — No Duplicate Document Table (CROSS-MODULE)

Assets & Property shall not create its own document storage table.

## AP-069 — Document Association (ERP)

The association between property/asset and documents shall use explicit
FK relationships. The exact mechanism (junction table or direct FK)
belongs in Table Design, respecting DOC-ARCH-001 (no polymorphic entity
FK).

---

# 19. Audit and Change History Boundary

## AP-070 — Standard Audit Metadata (ERP)

All Assets & Property tables shall carry the project standard audit
columns where applicable:

```text
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
deleted_at
deleted_by_sangha_sevi_pk
is_active
```

## AP-071 — Business-Significant Changes (ERP)

Business-significant field changes on property and asset records shall be
captured in `field_change_log` (Foundation-owned) per the Data Change
Architecture.

## AP-072 — Custodianship Is Inherently Historical (ERP)

The custodianship entity itself provides change history by design
(temporal records with effective_from / effective_to). It does not require
additional change-history infrastructure for its primary purpose.

---

# 20. Authorization

## AP-073 — No Module-Specific Approval Table (ERP)

Assets & Property shall not introduce a shared approval table. Approval
for acquisition/disposal belongs to the Governance module's authority
mechanisms.

## AP-074 — Access Control (ERP)

Access to Assets & Property data shall be governed by the centralized
RBAC framework (Administration module). Module-specific permissions may
be defined in the permission catalogue but do not require module-specific
authorization tables.

---

# 21. Explicitly Not Established

The following requirements are **not established** by the source and are
**not frozen** by this document:

| Requirement | Status |
|-------------|--------|
| Asset depreciation / book value | NOT FROZEN |
| Asset valuation (current market value) | NOT FROZEN |
| Insurance tracking | NOT FROZEN |
| Maintenance scheduling / recurring cycles | NOT FROZEN |
| Condition grading system | NOT FROZEN |
| Inspection lifecycle | NOT FROZEN |
| Warranty tracking | NOT FROZEN |
| Bar-code / QR-code asset tagging | NOT FROZEN |
| Rented/leased premises tracking | NOT FROZEN |
| Inventory counting / stock-take | NOT FROZEN |
| Asset categorization beyond movable/immovable | PENDING |
| Exact location model | PENDING (AP-022) |

These may be introduced through future business rules if supported by
source or explicit decision.

---

# 22. Rule Summary

| Rule ID | Classification | Summary |
|---------|---------------|---------|
| AP-001 | ERP | Separate property and asset entities |
| AP-002 | CONSTITUTIONAL | Property = immovable holdings |
| AP-003 | CONSTITUTIONAL | Asset = movable property |
| AP-004 | ERP | Property UUID primary key |
| AP-005 | ERP | Property human-readable ID |
| AP-006 | ERP | Asset UUID primary key |
| AP-007 | ERP | Asset human-readable ID |
| AP-008 | ERP | Identity uniqueness across namespaces |
| AP-009 | ERP | Holding arrangement distinct from custodianship |
| AP-010 | CONSTITUTIONAL | Kendra properties in name of Shri Shri Thakur |
| AP-011 | CONSTITUTIONAL | Mahila properties in President's name |
| AP-012 | ERP | No universal holding rule |
| AP-013 | PENDING | Holding arrangement normalization |
| AP-014 | CONSTITUTIONAL | Custodian = org unit with operational responsibility |
| AP-015 | ERP | Custodian is always an organization |
| AP-016 | ERP | Custodianship as separate entity |
| AP-017 | ERP | One active custodian per property/asset |
| AP-018 | ERP | Custodianship history preservation |
| AP-019 | ERP | Custodianship requires property or asset |
| AP-020 | CONSTITUTIONAL | Sakha office-bearers as custodians |
| AP-021 | ERP | Location is property/asset attribute |
| AP-022 | PENDING | Location representation |
| AP-023 | ERP | Acquisition record |
| AP-024 | CONSTITUTIONAL | Governing Body competent to acquire |
| AP-025 | CROSS-MODULE | Acquisition authority belongs to Governance |
| AP-026 | CROSS-MODULE | Acquisition payment belongs to Finance |
| AP-027 | CONSTITUTIONAL | Kendra maintenance responsibility |
| AP-028 | CONSTITUTIONAL | Mahila Kutir maintenance by Kendra |
| AP-029 | ERP | Maintenance as historical record |
| AP-030 | CONSTITUTIONAL | Maintenance types (repairs, improvements, etc.) |
| AP-031 | CROSS-MODULE | Maintenance expense belongs to Finance |
| AP-032 | PENDING | Maintenance scheduling not established |
| AP-033 | CONSTITUTIONAL | Article maintenance responsibility |
| AP-034 | ERP | Statutory obligations as separate records |
| AP-035 | CONSTITUTIONAL | Land revenue obligation |
| AP-036 | CONSTITUTIONAL | Municipal tax obligation |
| AP-037 | CONSTITUTIONAL | Land record maintenance |
| AP-038 | CONSTITUTIONAL | Revenue/municipal record requirement |
| AP-039 | CROSS-MODULE | Statutory payment belongs to Finance |
| AP-040 | ERP | Statutory records apply to property only |
| AP-041 | ERP | Transfer is not a property state |
| AP-042 | ERP | Transfer creates new custodianship |
| AP-043 | ERP | Transfer and location change are independent |
| AP-044 | CONSTITUTIONAL | Governing Body competent to dispose |
| AP-045 | CROSS-MODULE | Disposal authority belongs to Governance |
| AP-046 | ERP | Disposal is terminal |
| AP-047 | ERP | Retirement is terminal |
| AP-048 | CROSS-MODULE | Disposal proceeds belong to Finance |
| AP-049 | CONSTITUTIONAL | Kendra custodianship of specified properties |
| AP-050 | CONSTITUTIONAL | Governing Body may appoint property Manager |
| AP-051 | CONSTITUTIONAL | Governing Body frames property rules |
| AP-052 | CONSTITUTIONAL | Seva puja properties as Kendra property |
| AP-053 | CONSTITUTIONAL | Mahila Governing Body property competence |
| AP-054 | CONSTITUTIONAL | Mahila landed properties in President's name |
| AP-055 | CONSTITUTIONAL | Mahila earnings from landed properties |
| AP-056 | CONSTITUTIONAL | Mahila Kutir maintenance always by Kendra |
| AP-057 | CONSTITUTIONAL | Dissolution vesting in Kendra Sangha |
| AP-058 | ERP | Dissolution is not routine transfer |
| AP-059 | ERP | Vesting preserves history |
| AP-060 | CROSS-MODULE | No financial transaction tables |
| AP-061 | CROSS-MODULE | Business context only |
| AP-062 | CROSS-MODULE | Property income is Finance-owned |
| AP-063 | PENDING | No depreciation or valuation |
| AP-064 | CROSS-MODULE | Heritage does not own property records |
| AP-065 | CROSS-MODULE | No duplicate entity across Heritage/A&P |
| AP-066 | PENDING | Sacred articles boundary |
| AP-067 | CROSS-MODULE | Documents are Foundation-owned |
| AP-068 | CROSS-MODULE | No duplicate document table |
| AP-069 | ERP | Document association via explicit FK |
| AP-070 | ERP | Standard audit metadata |
| AP-071 | ERP | Business-significant changes to field_change_log |
| AP-072 | ERP | Custodianship is inherently historical |
| AP-073 | ERP | No module-specific approval table |
| AP-074 | ERP | Access control via centralized RBAC |

---

# 23. Classification Statistics

| Classification | Count |
|---------------|-------|
| CONSTITUTIONAL | 24 |
| ERP | 32 |
| CROSS-MODULE | 13 |
| PENDING | 5 |
| **Total** | **74** |

---

# 24. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```
