# NSS ERP — Foundation Entity Relationship Design

**Document ID:** SOL-FND-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Foundation
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
Foundation Module.

The current source-supported Foundation database consists of:

    master_category
    master_data
    system_setting
    id_sequence_master
    country
    state
    district
    city_village

Total:

    8 tables

---

# 2. Foundation ERD Boundary

The Foundation ERD is divided into four logical areas:

```text
Foundation
│
├── Master Data
│   ├── master_category
│   └── master_data
│
├── System Configuration
│   └── system_setting
│
├── Identifier Infrastructure
│   └── id_sequence_master
│
└── Geographic Reference
    ├── country
    ├── state
    ├── district
    └── city_village
```

---

# 3. High-Level ERD

```text
                    ┌────────────────────┐
                    │  master_category   │
                    └─────────┬──────────┘
                              │
                              │ 1:N
                              ▼
                    ┌────────────────────┐
                    │    master_data     │
                    └────────────────────┘


                    ┌────────────────────┐
                    │  system_setting   │
                    └────────────────────┘


                    ┌────────────────────┐
                    │ id_sequence_master │
                    └────────────────────┘


                    ┌────────────────────┐
                    │      country      │
                    └─────────┬──────────┘
                              │
                              │ 1:N
                              ▼
                    ┌────────────────────┐
                    │       state       │
                    └─────────┬──────────┘
                              │
                              │ 1:N
                              ▼
                    ┌────────────────────┐
                    │      district     │
                    └─────────┬──────────┘
                              │
                              │ 1:N
                              ▼
                    ┌────────────────────┐
                    │   city_village    │
                    └────────────────────┘
```

The `master_category → master_data` and geographic parent-child
relationships represent the logical Foundation model.

The exact physical FK definitions are finalized in Table Design.

---

# 4. `master_category`

## Purpose

`master_category` defines a logical category under which reusable master
values are maintained.

Conceptually:

```text
master_category
       │
       │ 1:N
       ▼
master_data
```

---

# 5. `master_data`

## Purpose

`master_data` contains reusable values belonging to a master category.

The generic master-data mechanism allows business modules to consume
centrally maintained values rather than duplicating hard-coded values.

---

# 6. Master Data Relationship

Logical relationship:

```text
master_category
       1
       │
       │
       N
       ▼
master_data
```

A category may contain multiple master-data values.

A master-data value belongs to its applicable category.

---

# 7. Master Data Example

Conceptually:

```text
MASTER CATEGORY
    MEMBERSHIP_STATUS
          │
          ├── ACTIVE
          ├── SUSPENDED
          └── CANCELLED
```

This is an example of the generic mechanism.

The complete master catalogue is maintained separately in the project's
Master Data Catalog.

---

# 8. Generic Master Architecture

The intended relationship is:

```text
Business Module
       │
       ▼
Master Category
       │
       ▼
Master Data
```

Business modules consume the approved master values.

They should not independently create duplicate representations of the same
common business value.

---

# 9. Master Data Boundary

The Foundation module owns the generic master-data mechanism.

It does not automatically own every business concept represented by a
master value.

For example:

```text
Foundation
    → Master Data mechanism

Membership
    → Membership business meaning

Governance
    → Governance business meaning
```

---

# 10. `system_setting`

## Purpose

`system_setting` stores centrally managed configurable system settings.

It is logically independent from the generic master-data relationship.

```text
system_setting
```

There is no source-supported requirement to make `system_setting` a child of
`master_category`.

---

# 11. System Setting Boundary

The ERD intentionally keeps:

```text
master_data
```

and:

```text
system_setting
```

as separate concepts.

Master Data represents reusable reference values.

System Settings represent configurable system behaviour or parameters.

---

# 12. `id_sequence_master`

## Purpose

`id_sequence_master` provides the centralized identifier-sequence
configuration used for approved business identifiers.

It is logically independent from:

```
master_category
master_data
system_setting
```

unless a future approved design establishes an explicit relationship.

---

# 13. Identifier Architecture

The logical sequence model is:

```text
Business Domain
      │
      ▼
id_sequence_master
      │
      ▼
Next Approved Identifier
```

The sequence infrastructure is shared across modules.

---

# 14. Sequence Ownership

Each business identifier sequence should have one authoritative sequence
definition.

Modules should not independently maintain competing sequence mechanisms for
the same identifier space.

---

# 15. Technical PK vs Business ID

The Foundation ERD supports the project distinction:

```text
Technical Primary Key
        ≠
Business Identifier
```

Technical PKs identify database records.

Business identifiers identify business entities according to the owning
domain's rules.

---

# 16. `country`

## Purpose

`country` provides the common geographic country reference.

It is part of the shared geographic master hierarchy.

---

# 17. `state`

## Purpose

`state` provides state/province-level geographic reference data.

Logical relationship:

```text
country
   1
   │
   N
   ▼
state
```

---

# 18. `district`

## Purpose

`district` provides district-level geographic reference data.

Logical relationship:

```text
state
   1
   │
   N
   ▼
district
```

---

# 19. `city_village`

## Purpose

`city_village` provides city/village/locality-level geographic reference
data.

Logical relationship:

```text
district
   1
   │
   N
   ▼
city_village
```

---

# 20. Geographic Hierarchy

The Foundation geographic hierarchy is:

```text
Country
   │
   └── State
          │
          └── District
                  │
                  └── City / Village
```

---

# 21. Geographic Integrity

The geographic hierarchy shall preserve valid parent-child relationships.

Conceptually:

```text
City/Village
     ↓
District
     ↓
State
     ↓
Country
```

An invalid parent reference shall not be permitted.

The exact database constraints are defined during Table Design.

---

# 22. Geographic vs Organization

The geographic hierarchy is NOT the NSS organizational hierarchy.

Foundation:

```text
Country
   ↓
State
   ↓
District
   ↓
City/Village
```

Organization:

```text
Kendra
   ↓
Anchalika
   ↓
Zilla
   ↓
Sakha
```

These are separate domains.

---

# 23. Geographic Data Consumers

The geographic Foundation data may be referenced by multiple modules.

Examples include:

```
Person
Family
Organization
Other approved location-bearing entities
```

The consuming module remains responsible for the business meaning of the
location.

---

# 24. No Duplicate Geographic Masters

Business modules shall not create duplicate generic geographic tables where
the Foundation geographic hierarchy already provides the required reference
data.

---

# 25. Organization Dependency

The Organization Module may consume geographic reference data.

However:

```text
Geographic Data
        ≠
Organization Structure
```

Foundation remains responsible for the geographic reference hierarchy.

Organization remains responsible for the NSS organizational hierarchy.

---

# 26. Person Dependency

Person may reference geographic masters for address/location information.

Foundation does not own Person.

---

# 27. Family Dependency

Family may reference geographic masters where family location information is
required.

Foundation does not own Family.

---

# 28. Master Data Dependency

Business modules may reference `master_data` where the relevant business
concept has been approved for generic master-data treatment.

---

# 29. Master Data Ownership

The logical ownership is:

```text
master_category
       │
       ▼
master_data
```

The category defines the semantic grouping.

The value provides the reusable reference value.

---

# 30. System Setting Independence

The ERD deliberately does not force:

```text
system_setting
       ↓
master_category
```

because the source does not establish such a relationship.

---

# 31. Sequence Independence

The ERD deliberately does not force:

```text
id_sequence_master
       ↓
master_data
```

or:

```text
id_sequence_master
       ↓
system_setting
```

because the source does not establish such relationships.

---

# 32. Foundation ERD — Complete Logical View

```text
                           FOUNDATION
                               │
          ┌────────────────────┼─────────────────────┐
          │                    │                     │
          ▼                    ▼                     ▼
   MASTER DATA          SYSTEM CONFIGURATION   ID SEQUENCES
          │                    │                     │
          ▼                    ▼                     ▼
 master_category         system_setting       id_sequence_master
          │
          │ 1:N
          ▼
    master_data


                    GEOGRAPHIC REFERENCE
                             │
                             ▼
                         country
                             │
                             │ 1:N
                             ▼
                           state
                             │
                             │ 1:N
                             ▼
                         district
                             │
                             │ 1:N
                             ▼
                       city_village
```

---

# 33. Cross-Module Foundation Model

```text
                    FOUNDATION
                        │
       ┌────────────────┼────────────────┐
       │                │                │
       ▼                ▼                ▼
  Master Data       Geographic       Sequences
       │             Masters             │
       │                │                │
       └────────┬───────┴────────────────┘
                │
                ▼
          Business Modules
```

---

# 34. No Business Transaction Tables

The Foundation ERD does not contain domain transaction entities such as:

```
Membership Renewal
Attendance
Governance Election
Sevak Assignment
UPBS Registration
Publication Purchase
```

Those belong to their respective modules.

---

# 35. No Authentication Tables

The Foundation ERD does not contain:

```
user_account
password_history
role_master
permission_master
user_role
role_permission
admin_scope
```

Those belong to Authentication & Security / Administration.

---

# 36. No Person Table

The Foundation ERD does not contain:

```
person
```

Person remains a separate module.

---

# 37. No Organization Table

The Foundation ERD does not contain:

```
organization
```

Organization remains a separate module.

---

# 38. No Audit Tables

The Foundation ERD does not introduce:

```
audit_master
system_event_log
```

Audit remains a separate common capability.

---

# 39. No Document Tables

The Foundation ERD does not introduce Document Management tables.

Document storage/management remains a separate capability.

---

# 40. ERD Relationship Matrix

| Source               | Target         | Relationship | Status                 |
| -------------------- | -------------- | ------------ | ---------------------- |
| `master_category`    | `master_data`  | 1:N          | Logical/source-aligned |
| `country`            | `state`        | 1:N          | Logical/source-aligned |
| `state`              | `district`     | 1:N          | Logical/source-aligned |
| `district`           | `city_village` | 1:N          | Logical/source-aligned |
| `system_setting`     | —              | Standalone   | Source-aligned         |
| `id_sequence_master` | —              | Standalone   | Source-aligned         |

---

# 41. Relationship Not Assumed

The following relationships are deliberately NOT introduced:

```text
system_setting → master_category

system_setting → master_data

id_sequence_master → master_category

id_sequence_master → master_data

country → master_category

organization → city_village
```

unless a later approved design explicitly requires them.

---

# 42. Primary-Key Boundary

Each Foundation table shall have its own technical primary key according to
the project database standard.

Logical PK naming:

```text
master_category_pk
master_data_pk
system_setting_pk
id_sequence_master_pk
country_pk
state_pk
district_pk
city_village_pk
```

The exact physical types and generation strategy belong to Table Design.

---

# 43. Foreign-Key Boundary

The confirmed logical FK relationships are:

```text
master_data
    → master_category

state
    → country

district
    → state

city_village
    → district
```

The exact FK column names and delete behaviour are finalized in Table
Design.

---

# 44. Parent-Child Integrity

Geographic parent-child relationships must remain structurally valid.

For example:

```text
district.state
    →
state

city_village.district
    →
district
```

---

# 45. Historical Geographic Integrity

The final database design must consider the effect of geographic master
changes on historical business records.

Deactivating a geographic reference should not casually invalidate historical
records.

The exact lifecycle behaviour is finalized in Business Rules and Table
Design.

---

# 46. Master Value Lifecycle

The ERD supports the possibility that a `master_data` value becomes
inactive without deleting its historical references.

The exact lifecycle fields are defined in Table Design.

---

# 47. Sequence Lifecycle

`id_sequence_master` represents sequence configuration.

The exact sequence-state and concurrency behaviour are implementation
concerns and are not frozen by this ERD.

---

# 48. System Setting Lifecycle

`system_setting` represents configurable settings.

The ERD does not prescribe versioning/history tables for settings.

---

# 49. Database Integrity

The final PostgreSQL design shall enforce appropriate:

```
Primary Keys
Foreign Keys
Unique Constraints
NOT NULL Constraints
CHECK Constraints
```

according to the approved Table Design.

---

# 50. Indexing Boundary

The final implementation should support efficient lookups for:

```
Master Category → Master Data
Country → State
State → District
District → City/Village
```

Appropriate FK indexes shall be defined during Table Design.

---

# 51. Foundation Data Flow

```text
Master Category
      │
      ▼
Master Data
      │
      ▼
Business Modules

Country
   │
   ▼
State
   │
   ▼
District
   │
   ▼
City/Village
   │
   ▼
Business Location References

ID Sequence
   │
   ▼
Business Identifier Generation

System Setting
   │
   ▼
Approved Configurable Behaviour
```

---

# 52. Core Foundation ERD Principle

The Foundation ERD provides shared reference and configuration infrastructure
without absorbing ownership of business domains.

The design therefore follows:

```text
Common Infrastructure
        ↓
Foundation

Business Meaning
        ↓
Owning Business Module
```

---

# 53. Current Frozen Entity Set

```text
master_category
master_data

system_setting

id_sequence_master

country
state
district
city_village
```

Total:

```
8 tables
```

---

# 54. DDL Boundary

This ERD does not define:

```
Exact column lists
Exact data types
Exact constraints
Exact indexes
Exact seed data
Exact sequence implementation
Exact geographic lifecycle
```

Those belong to:

```
FOUNDATION-03 — Business Rules
FOUNDATION-04 — Table Design
```

---

# 55. Source Alignment

The PostgreSQL schema review explicitly classifies the following eight
tables under Foundation:

```
master_category
master_data
system_setting
id_sequence_master
country
state
district
city_village
```

The database build plan separately defines:

```
03_master_tables.sql
04_system_setting.sql
05_geo_tables.sql
```

and identifies the generic master framework and geographic tables.

The project architecture establishes Foundation as the shared common layer
rather than a business-transaction module.

---

# 56. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
