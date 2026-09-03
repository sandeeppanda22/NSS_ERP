# NSS ERP — Organization Table Design

**Document ID:** SOL-ORG-005  
**Version:** 1.3.0  
**Status:** DRAFT — GOVERNANCE ALIGNED  
**Module:** Organization  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the NSS ERP
Organization Module.

It translates the approved:

- Organizational Governance Standard
- Organization Module Overview
- Organization ERD
- Organization Lifecycle
- Organization Business Rules

into a table-level logical design.

This document defines logical data ownership and relationships.

It does not define PostgreSQL DDL, Django migrations, physical indexes,
triggers, or implementation-specific database syntax.

---

# 2. Governing Source

The primary governing source for the Organization Module is:

```text
GOV-002 — Organizational Governance Standard
```

GOV-002 requires the ERP to maintain:

* parent organization;
* child organization;
* reporting lineage;
* hierarchical level; and
* organizational status.

The NSS Bye-Law remains the supreme authority for the actual
statutory organizational structure.

---

# 3. Current Frozen Table Scope

The current Organization Module contains three tables:

```text
organization_type_master
organization_status_master
organization
```

Therefore:

```text
Organization Module
│
├── organization_type_master
├── organization_status_master
└── organization
```

No fourth Organization table is introduced by this document.

---

# 4. Explicitly Excluded Tables

The current design does not contain:

```text
organization_address
organization_address_history
organization_hierarchy
organization_level_master
```

The absence of these tables does not mean that their corresponding business
concepts are necessarily unsupported.

In particular:

```text
Hierarchical Level
=
Required Business Attribute
```

but:

```text
organization_level_master
=
Not currently defined
```

by the authoritative source.

---

# 5. Design Principle — Logical Requirement vs Physical Representation

The Organization Module distinguishes between:

```text
Business Requirement
        ↓
Logical Data Attribute
        ↓
Physical Database Implementation
```

GOV-002 establishes the business requirement that hierarchical level shall
be maintained.

It does not prescribe:

* a separate level master table;
* a numeric representation;
* a text representation;
* an enum;
* a calculated value; or
* a specific PostgreSQL datatype.

Therefore the solution design records the requirement without inventing an
unsupported physical implementation.

---

# 6. Organization Tables

| # | Table                        | Purpose                                  |
| - | ---------------------------- | ---------------------------------------- |
| 1 | `organization_type_master`   | Controlled organization classification   |
| 2 | `organization_status_master` | Controlled organization lifecycle status |
| 3 | `organization`               | Organizational entity and hierarchy node |

---

# 7. Table — `organization_type_master`

## Purpose

Stores the controlled classification of organizational units.

Organization type is maintained separately from the organizational entity
itself.

---

# 8. `organization_type_master` — Logical Columns

| Column                   | Required | Key    | Description              |
| ------------------------ | -------: | ------ | ------------------------ |
| `organization_type_pk`   |      Yes | PK     | Internal primary key     |
| `organization_type_code` |      Yes | UNIQUE | Stable type code         |
| `organization_type_name` |      Yes | —      | Human-readable type name |
| `description`            |       No | —      | Type description         |
| `sort_order`             |       No | —      | Presentation ordering    |
| `created_at`             |      Yes | —      | Creation timestamp       |
| `updated_at`             |      Yes | —      | Last update timestamp    |

---

# 9. Organization Type Code

`organization_type_code` provides the stable machine-readable value for the
organization type.

The actual statutory type vocabulary shall come from approved
authoritative/project master-data sources.

This document does not independently create new statutory organization
types.

---

# 10. Organization Type Name

`organization_type_name` stores the human-readable organization type.

It may be used in:

* Organization screens
* Search
* Reports
* Dashboards
* Administrative interfaces

---

# 11. Organization Type Description

`description` provides supporting explanatory information.

It shall not be used to create statutory meaning that is absent from
the authoritative source.

---

# 12. Organization Type Ordering

`sort_order` may control display ordering.

It does not establish:

* statutory hierarchy;
* parent-child compatibility; or
* reporting authority.

---

# 13. Table — `organization_status_master`

## Purpose

Stores controlled organizational lifecycle/status values.

---

# 14. `organization_status_master` — Logical Columns

| Column                     | Required | Key    | Description           |
| -------------------------- | -------: | ------ | --------------------- |
| `organization_status_pk`   |      Yes | PK     | Internal primary key  |
| `organization_status_code` |      Yes | UNIQUE | Stable status code    |
| `organization_status_name` |      Yes | —      | Human-readable status |
| `description`              |       No | —      | Status description    |
| `sort_order`               |       No | —      | Presentation ordering |
| `created_at`               |      Yes | —      | Creation timestamp    |
| `updated_at`               |      Yes | —      | Last update timestamp |

---

# 15. Lifecycle Status Vocabulary

GOV-002 identifies the following as typical organizational lifecycle states:

```text
PROPOSED
APPROVED
ACTIVE
INACTIVE
ARCHIVED
```

The word "typical" is important.

This table therefore represents the current documented lifecycle vocabulary
without claiming that GOV-002 provides a complete exhaustive transition
matrix.

---

# 16. Status Code

`organization_status_code` is the stable machine-readable status.

Examples:

```text
PROPOSED
APPROVED
ACTIVE
INACTIVE
ARCHIVED
```

---

# 17. Status Name

`organization_status_name` stores the human-readable lifecycle status.

---

# 18. Status Ordering

`sort_order` is presentation metadata.

It shall not be interpreted as the authoritative lifecycle transition order.

Lifecycle transitions are governed by the Organization Lifecycle and
applicable governance procedures.

---

# 19. Table — `organization`

## Purpose

`organization` is the central Organization entity.

It represents:

* Organizational identity
* Organization classification
* Current lifecycle status
* Parent-child relationship
* Hierarchical level
* Organizational lineage
* Current organization address

---

# 20. `organization` — Logical Columns

| Column                   |    Required | Key    | Description                                |
| ------------------------ | ----------: | ------ | ------------------------------------------ |
| `organization_pk`        |         Yes | PK     | Internal primary key                       |
| `organization_id`        |         Yes | UNIQUE | Permanent business identifier              |
| `organization_name`      |         Yes | —      | Human-readable organization name           |
| `organization_type_pk`   |         Yes | FK     | Organization type                          |
| `organization_status_pk` |         Yes | FK     | Current lifecycle status                   |
| `parent_organization_pk` | Conditional | FK     | Immediate parent organization              |
| `address_line_1`         |          No | —      | Current address line 1                     |
| `address_line_2`         |          No | —      | Current address line 2                     |
| `district_pk`            |          No | FK     | District reference                         |
| `state_pk`               |          No | FK     | State/province reference                   |
| `country_pk`             |          No | FK     | Country reference                          |
| `city_village_pk`        |          No | FK     | City/village reference                     |
| `postal_code_pk`         |          No | FK     | Postal/PIN code reference                  |
| `latitude`               |          No | —      | Physical location latitude                 |
| `longitude`              |          No | —      | Physical location longitude                |
| `created_at`             |         Yes | —      | Creation timestamp                         |
| `updated_at`             |         Yes | —      | Last update timestamp                      |

**Note on hierarchical level:** GOV-002 requires the ERP to maintain
hierarchical level. This requirement is satisfied without a stored column:

* **Organizational level** (what kind of unit this is) is determined by
  `organization_type_pk`.
* **Hierarchy depth** (distance from root) is derived from
  `parent_organization_pk` via recursive traversal when required.

Storing a redundant `hierarchical_level` column would risk divergence from
the actual parent chain and would require a physical type decision that the
authoritative source does not prescribe.

---

# 21. `organization_pk`

Internal primary key for the organization entity.

It exists for database relationships and is not the public/business
organization identifier.

---

# 22. `organization_id`

Permanent business identifier of the organization.

Rules:

* Unique
* System-generated
* Stable
* Immutable after creation
* Never reused
* Referenced consistently across ERP modules

This directly implements GOV-DATA-004. 

---

# 23. `organization_name`

Human-readable organizational name.

The organization name is not the permanent organizational identity.

An approved name change does not automatically create a new organization.

---

# 24. `organization_type_pk`

Foreign key to:

```text
organization_type_master.organization_type_pk
```

It identifies the controlled organizational type.

---

# 25. `organization_status_pk`

Foreign key to:

```text
organization_status_master.organization_status_pk
```

It identifies the organization's current lifecycle status.

---

# 26. `parent_organization_pk`

Self-referencing foreign key:

```text
organization.parent_organization_pk
        ↓
organization.organization_pk
```

It identifies the immediate parent organization.

---

# 27. Parent Rule

Every non-apex organization shall have exactly one valid parent.

The apex organization is the only organization permitted to have no parent.

This directly implements GOV-ORG-003 and GOV-DATA-001.

---

# 28. Apex Rule

The apex organization has:

```text
parent_organization_pk = NULL
```

Exactly one apex organization shall exist in the production organizational
hierarchy.

---

# 29. Child Relationship

The self-reference permits:

```text
Parent Organization
        │
        ├── Child Organization
        ├── Child Organization
        └── Child Organization
```

One parent may have multiple children.

---

# 30. No Multiple Parents

A child organization may have only one immediate parent.

The current logical model contains a single:

```text
parent_organization_pk
```

attribute.

---

# 31. No Circular Hierarchy

The implementation shall prevent:

```text
A → B
B → C
C → A
```

Circular organizational relationships are prohibited by GOV-002. 

---

# 32. No Orphan Organizations

A non-apex organization cannot have:

```text
parent_organization_pk = NULL
```

---

# 33. Hierarchical Level — Resolved Design Decision

GOV-002 requires the ERP to maintain hierarchical level as part of
organizational relationships.

The term "hierarchical level" conflates two distinct concepts:

1. **Organizational type/constitutional level** — what kind of unit this is
   (KENDRA, ZILLA, ANCHALIKA, SAKHA, etc.). This is already represented by
   `organization_type_pk`.

2. **Tree depth** — how many parent hops separate this organization from the
   apex. This is derived from `parent_organization_pk` via recursive CTE.

Neither concept requires a stored column. Therefore:

```text
hierarchical_level
    =
NOT a physical column in the organization table
```

This decision is driven by two facts:

* The authoritative source does not prescribe a physical type or encoding.
* The NSS organizational hierarchy permits alternative intermediate levels
  (Anchalika and Zilla are peers, not ordered predecessors — §36.1), so
  any fixed ordinal mapping would be incorrect.

---

# 34. Hierarchical Level — No Separate Master

The current authoritative source does not establish:

```text
organization_level_master
```

Therefore no such table is part of the Organization Module.

---

# 35. Hierarchical Level — Query-Time Derivation

When reports, permissions, or workflows require hierarchical depth, it
shall be computed at query time:

```sql
WITH RECURSIVE org_tree AS (
    SELECT organization_pk, parent_organization_pk, 0 AS depth
    FROM organization
    WHERE parent_organization_pk IS NULL
    UNION ALL
    SELECT o.organization_pk, o.parent_organization_pk, t.depth + 1
    FROM organization o
    JOIN org_tree t ON o.parent_organization_pk = t.organization_pk
)
SELECT * FROM org_tree;
```

For the NSS hierarchy (max ~4 levels deep), this is trivially performant.

---

# 36. Actual NSS Organizational Hierarchy (Frozen)

The NSS organizational hierarchy is:

```text
Kendra → Anchalika/Zilla → Sakha
```

Anchalika and Zilla are **alternative intermediate organizational levels**.
Neither is required to precede the other. Both of the following are valid
organizational structures:

```text
Kendra → Anchalika → Sakha
Kendra → Zilla → Sakha
```

The rare case:

```text
Kendra → Zilla → Anchalika → Sakha
```

is also structurally possible.

This reinforces the derivation decision: a fixed ordinal level column
cannot correctly represent alternative intermediate structures.

---

# 37. Hierarchical Level vs Organization Type

These are separate concepts:

```text
Organization Type
        ≠
Hierarchical Level
```

An organization type classifies an entity. Hierarchical position describes
where it sits in the parent chain.

`organization_type_pk` answers "what is this organization?"
`parent_organization_pk` answers "where does it sit?"

No additional column is needed.

---

# 38. Hierarchical Position vs Reporting Lineage

Reporting lineage represents the path:

```text
Organization
    ↓
Parent
    ↓
Parent
    ↓
Apex
```

Hierarchical level represents the organization's position within that
structure.

The two concepts must not be conflated.

---

# 40. Organizational Lineage

The parent relationship shall allow complete lineage traversal to the apex.

GOV-DATA-003 requires this lineage to remain available for:

* Reports
* Workflows
* Permissions
* Governance processes. 

---

# 41. Lineage Preservation

Organizational status or metadata changes shall not destroy the ability to
trace an organization to its apex.

---

# 42. Reporting Lineage

The organization model must support determination of:

```text
Organization
    ↓
Immediate Parent
    ↓
Higher Parent
    ↓
Apex
```

without ambiguity.

---

# 43. Organization Address

The current v1 design stores the current organization address directly on
`organization`.

Fields:

```text
address_line_1
address_line_2
district_pk
state_pk
country_pk
city_village_pk
postal_code_pk
latitude
longitude
```

`city_village_pk` and `postal_code_pk` reference Foundation geography
entities. The selected city_village + postal_code combination is validated
against the Foundation `city_village_postal_code_map` at the application
layer.

`latitude` and `longitude` represent the physical location of the
organization. These are distinct from Foundation geography — they record
the actual coordinates of a specific organizational unit, not geographic
reference data.

---

# 44. No `organization_address`

The following table is not part of the current design:

```text
organization_address
```

The project source explicitly revised the earlier proposal to place the
address directly on `organization`. 

---

# 45. Address Cardinality

Current design:

```text
One Organization
      ↓
Zero or One Current Address
```

No multiple active organization addresses are defined in v1.

---

# 46. No Address History Table

The current Organization design does not include:

```text
organization_address_history
```

Historical address requirements are outside the current frozen scope.

---

# 47. Location Master References

The Organization Module reuses common Location Master data.

Logical references include:

```text
district_pk
state_pk
country_pk
city_village_pk
postal_code_pk
```

The Organization Module does not own duplicate geographic master tables.

`latitude` and `longitude` are Organization-owned attributes — they
represent the physical location of a specific organizational unit, not
Foundation geography reference data.

---

# 48. Administrative vs Physical Location (FROZEN)

The frozen organization type list (8 types):

```text
KENDRA          = Central Body (unique)
NILACHALA_KUTIRA = Spiritual Residence (unique)
SMRUTI_MANDIRA  = Memorial Temple (unique)
ANCHALIKA       = Administrative Unit (multiple)
ZILLA           = Administrative Unit (multiple)
SAKHA           = Physical Sangha Location (multiple)
SAKHA_ASANA     = Approved Sakha, no own building (multiple)
PATHA_CHAKRA    = Study Circle (multiple)
```

Therefore physical-address requirements shall not automatically be imposed
on every organizational unit. 

---

# 49. Organization Type Relationship

```text
organization_type_master
          1
          │
          │
          N
          ▼
organization
```

One organization type may classify multiple organizations.

---

# 50. Organization Status Relationship

```text
organization_status_master
          1
          │
          │
          N
          ▼
organization
```

One status may apply to multiple organizations.

---

# 51. Organization Hierarchy Relationship

```text
organization
     1
     │
     │ parent
     │
     N
     ▼
organization
```

The organization table is therefore both:

```text
Organizational Entity
+
Hierarchy Node
```

---

# 52. Complete Organization Logical Model

```text
organization_type_master
            │
            │ 1:N
            ▼
       organization
            ▲
            │
            │ 1:N self-reference
            │
       organization
            ▲
            │
            │
organization_status_master
```

with:

```text
organization
    ├── hierarchical_level
    ├── parent_organization_pk
    └── location references
```

---

# 53. Foreign Key Summary

| Child Table    | Column                   | Parent                       |
| -------------- | ------------------------ | ---------------------------- |
| `organization` | `organization_type_pk`   | `organization_type_master`   |
| `organization` | `organization_status_pk` | `organization_status_master` |
| `organization` | `parent_organization_pk` | `organization`               |
| `organization` | `district_pk`            | Common District Master       |
| `organization` | `state_pk`               | Common State Master          |
| `organization` | `country_pk`             | Common Country Master        |
| `organization` | `city_village_pk`        | Common City/Village Master   |
| `organization` | `postal_code_pk`         | Common Postal Code Master    |

---

# 54. Integrity Requirements

The logical design requires:

```text
organization_id
    → unique

organization_type_pk
    → valid reference

organization_status_pk
    → valid reference

parent_organization_pk
    → valid reference when non-apex

parent-child hierarchy
    → acyclic

organizational root
    → exactly one
```

---

# 55. Database and Application Enforcement

Critical Organization integrity shall be enforced through:

```text
Database Constraints
+
Application Validation
```

GOV-DATA-001 explicitly requires parent-child integrity to be enforced at
both levels. 

---

# 56. Apex Integrity

The implementation shall ensure:

```text
Exactly One
organization
WHERE
parent_organization_pk IS NULL
```

within the production organizational hierarchy.

---

# 57. Hierarchy Integrity

The implementation shall prevent:

```text
Multiple Parents
Circular Relationships
Orphan Units
Multiple Roots
Invalid Parent References
```

---

# 58. Organization Type Integrity

Every organization shall reference a valid organization type.

The type must originate from controlled master data.

---

# 59. Organization Status Integrity

Every organization shall reference a valid organization status.

Status values shall originate from controlled master data.

---

# 60. Hierarchical Level Integrity

Hierarchical level is derived, not stored (§33). Integrity is enforced
through:

* `organization_type_pk` — ensures the organization has a valid type
* `parent_organization_pk` — ensures valid parent chain
* Application validation — ensures parent-type-to-child-type compatibility

---

# 61. Governance Change Boundary

Changes affecting:

* hierarchy;
* hierarchical levels;
* organizational relationships;
* organizational types; or
* organizational governance

shall follow the applicable governance change-control process.

---

# 62. Organization Identity Preservation

Changes to:

* name;
* status;
* address;
* parent relationship;
* other approved organizational metadata

do not automatically create a new organization.

The permanent organization identifier remains stable unless an authoritative
decision establishes a genuinely new organization.

---

# 63. Historical Preservation

Inactive and archived organizations remain identifiable.

Their:

```text
organization_pk
organization_id
historical relationships
```

shall remain traceable according to the common audit/history framework.

---

# 64. Audit Fields

The logical Organization entity contains:

```text
created_at
updated_at
```

The implementation shall follow the common project Audit Standard.

---

# 65. Organizational Change Audit

Where applicable, the following changes shall be auditable:

```text
Organization Creation
Organization Name Change
Organization Type Change
Organization Status Change
Parent Change
Address Change
```

---

# 66. No Physical Deletion as Normal Lifecycle

The normal Organization lifecycle uses:

```text
INACTIVE
ARCHIVED
```

rather than physical deletion.

---

# 67. Specialized Module Boundary

Specialized modules may reference the organization but shall not duplicate
the core organizational identity.

Applicable modules include:

```text
Sevak
Mahila
Kumari
Kishori
Kishor
Governance
Membership
Attendance
Reports
```

---

# 68. Person Boundary

Person identity belongs to the Person Module.

No general person identity columns shall be added to `organization`.

---

# 69. Membership Boundary

Membership lifecycle belongs to the Membership Module.

No membership lifecycle columns shall be added to `organization`.

---

# 70. Governance Boundary

Governance owns:

```text
Governing Body
Position
Office-Bearer Assignment
Term
Election/Selection
```

The Organization Module owns the organization itself.

---

# 71. Attendance Boundary

Attendance belongs to the Attendance Module.

Attendance shall not determine Organization identity.

---

# 72. No Specialized Organization Tables

The current Organization design does not create separate organization master
tables such as:

```text
sakha_sangha
mahila_sangha
sikshya_kendra
sakha_asana
paribarik_asana
patha_chakra
```

unless an approved future design establishes a genuine separate entity.

---

# 73. No `organization_hierarchy`

The current hierarchy is represented through:

```text
organization.parent_organization_pk
```

A separate hierarchy table is not currently required.

---

# 74. No `organization_level_master`

The current authoritative source requires hierarchical level to be maintained,
but does not require or define a separate level master.

Therefore:

```text
organization_level_master
```

is not part of the current table count.

---

# 75. Hierarchical Level — Future Extension

If later authoritative requirements establish:

* named hierarchy levels;
* level metadata;
* level-specific rules;
* level-to-type mappings; or
* level-specific governance,

a separate master table or stored column may be considered through formal
design change.

The current decision (§33) is to derive hierarchical level from
`organization_type_pk` and `parent_organization_pk`.

---

# 76. Current Table Count

```text
organization_type_master       1
organization_status_master     1
organization                     1
─────────────────────────────────
TOTAL                            3
```

---

# 77. Current Organization Model

```text
┌──────────────────────────────────┐
│ organization_type_master         │
├──────────────────────────────────┤
│ organization_type_pk PK          │
│ organization_type_code UNIQUE    │
│ organization_type_name           │
│ description                      │
│ sort_order                       │
│ created_at                       │
│ updated_at                       │
└───────────────┬──────────────────┘
                │
                │ 1:N
                ▼
┌──────────────────────────────────┐
│ organization                     │
├──────────────────────────────────┤
│ organization_pk PK               │
│ organization_id UNIQUE           │
│ organization_name                │
│ organization_type_pk FK          │
│ organization_status_pk FK        │
│ parent_organization_pk FK        │
│ address_line_1                   │
│ address_line_2                   │
│ district_pk FK                   │
│ state_pk FK                      │
│ country_pk FK                    │
│ city_village_pk FK               │
│ postal_code_pk FK                │
│ latitude                         │
│ longitude                        │
│ created_at                       │
│ updated_at                       │
└───────────────┬──────────────────┘
                │
                │ self-reference
                ▼
        Parent Organization

┌──────────────────────────────────┐
│ organization_status_master       │
├──────────────────────────────────┤
│ organization_status_pk PK        │
│ organization_status_code UNIQUE  │
│ organization_status_name         │
│ description                      │
│ sort_order                       │
│ created_at                       │
│ updated_at                       │
└──────────────────────────────────┘
```

---

# 78. Final Logical Organization Entity

The Organization entity therefore contains five major logical areas:

```text
1. Identity
   organization_pk
   organization_id
   organization_name

2. Classification
   organization_type_pk

3. Lifecycle
   organization_status_pk

4. Hierarchy
   parent_organization_pk

5. Current Location
   address_line_1
   address_line_2
   district_pk
   state_pk
   country_pk
   city_village_pk
   postal_code_pk
   latitude
   longitude

(Hierarchical level is derived from organization_type_pk and
parent_organization_pk — see §33)
```

---

# 79. Important Design Decision

The Organization Module now explicitly satisfies the GOV-002 requirement
to maintain:

```text
Parent Organization
Child Organization
Reporting Lineage
Hierarchical Level
Organizational Status
```

without introducing an unsupported fourth Organization table.

GOV-002 explicitly requires these organizational relationships to be
maintained. 

---

# 80. What Is Frozen

The following are now frozen at the logical solution level:

```text
✓ 3 Organization tables

✓ organization is the central entity

✓ organization is the hierarchy node

✓ parent_organization_pk represents immediate parent

✓ exactly one parent for every non-apex organization

✓ one apex organization

✓ complete lineage to apex

✓ hierarchical level is derived from organization_type_pk and
  parent_organization_pk — no stored column

✓ organization type is master-driven

✓ organization status is master-driven

✓ permanent organization identifier

✓ organization identifier is unique

✓ organization identifier is never reused

✓ current address is directly on organization

✓ no organization_address table

✓ no organization_hierarchy table

✓ no organization_level_master table
```

---

# 81. What Is Not Yet Physically Frozen

The following remain implementation decisions:

```text
Exact PostgreSQL constraints

Exact PostgreSQL indexes

Exact database enforcement of single-root condition

Parent-type-to-child-type compatibility matrix
```

These shall be finalized during physical database design.

---

# 82. Why This Design Is Correct

The design does not ignore GOV-002.

Instead:

```text
GOV-002
  │
  ├── Parent Organization ───────► parent_organization_pk
  │
  ├── Child Organization ────────► self relationship
  │
  ├── Reporting Lineage ─────────► parent traversal
  │
  ├── Hierarchical Level ────────► derived from type + parent chain (§33)
  │
  └── Organizational Status ─────► organization_status_pk
```

This preserves the governance requirement while avoiding unsupported schema
assumptions.

---

# 83. Physical Database Boundary

This document does not define:

```text
CREATE TABLE
ALTER TABLE
CHECK CONSTRAINT
FOREIGN KEY SQL
INDEX SQL
TRIGGER SQL
PostgreSQL datatype selection
Django Model implementation
```

Those belong to the physical database implementation stage.

---

# 84. Final Organization Table Design Principle

The Organization Module shall maintain:

```text
ONE ORGANIZATION ENTITY
        │
        ├── Permanent Identity
        ├── Organization Type
        ├── Organization Status
        ├── Parent Organization
        ├── Organizational Lineage
        └── Current Address

(Hierarchical level derived from type + parent chain)
```

while preserving:

```text
ONE STATUTORY ROOT
ONE PARENT PER NON-APEX UNIT
NO CIRCULARITY
NO ORPHANS
COMPLETE LINEAGE
```

---

# 85. Status

```text
DOCUMENT STATUS:
DRAFT — GOVERNANCE ALIGNED

VERSION:
1.3.0

CHANGE LOG:
1.3.0 — Reconciled location fields with Foundation geography:
        postal_code (VARCHAR) → postal_code_pk (FK to postal_code);
        added city_village_pk (FK to city_village);
        added latitude, longitude (physical coordinates).
```

---

# End of Document
