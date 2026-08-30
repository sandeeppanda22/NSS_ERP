# NSS ERP — Foundation Table Design

**Document ID:** SOL-FND-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Foundation
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the Foundation
Module.

The Foundation Module provides:

- Generic Master Data
- System Settings
- Identifier Sequence Infrastructure
- Geographic Reference Data

The current frozen Foundation schema contains exactly eight tables, plus
two shared-infrastructure tables added by architectural decisions:

    master_category
    master_data
    system_setting
    id_sequence_master
    country
    state
    district
    city_village
    document_master        (DOC-ARCH-001, 2026-08-26 — shared document registry)
    field_change_log       (Data Change Architecture, 2026-08-26 — shared change log)

---

# 2. Source Boundary

The PostgreSQL schema review explicitly identifies the original eight tables
as the Foundation Module.

Two additional shared-infrastructure tables have been assigned to Foundation
by architectural decisions during the pre-DB gate (2026-08-26):

- `document_master` — DOC-ARCH-001 (moved from Person; shared document registry)
- `field_change_log` — Data Change Architecture (shared field-change tracking)

The database build plan identifies the implementation sequence as:

    03_master_tables.sql
    04_system_setting.sql
    05_id_sequence_master.sql
    06_geo_tables.sql

---

# 3. Table Inventory

| # | Table | Purpose |
|---:|---|---|
| 1 | `master_category` | Generic master-data category |
| 2 | `master_data` | Generic reusable master values |
| 3 | `system_setting` | Central system configuration |
| 4 | `id_sequence_master` | Business identifier sequence infrastructure |
| 5 | `country` | Geographic country master |
| 6 | `state` | State/province master |
| 7 | `district` | District master |
| 8 | `city_village` | City/village/locality master |
| 9 | `document_master` | Shared document registry (DOC-ARCH-001, moved from Person) |
| 10 | `field_change_log` | Shared field-change tracking (Data Change Architecture) |

---

# 4. Common Database Standards

All Foundation tables shall follow the project-wide database standards
where applicable.

## 4.1 Technical Primary Key

The project standard uses:

    <table_name>_pk

Examples:

    master_category_pk
    master_data_pk
    system_setting_pk
    id_sequence_master_pk
    country_pk
    state_pk
    district_pk
    city_village_pk

---

## 4.2 Primary Key Type

The project database architecture uses UUID technical primary keys.

Therefore the Foundation tables shall use UUID-based technical PKs.

---

## 4.3 Business Identifier

Where a Foundation entity requires a human/business identifier, it shall be
separate from the technical PK.

Example:

    country_pk
    country_code

The technical PK remains the relational identifier.

---

# 5. Audit Metadata

The project database standard identifies the following audit/lifecycle
fields for applicable tables:

    created_at
    created_by_sangha_sevi_pk

    updated_at
    updated_by_sangha_sevi_pk

    deleted_at
    deleted_by_sangha_sevi_pk

    is_active

Applicability to each Foundation reference table shall be finalized based on
its lifecycle.

---

# 6. `master_category`

## 6.1 Purpose

Defines a logical category for generic master values.

Relationship:

    master_category
          1
          │
          N
          ▼
    master_data

---

## 6.2 Primary Key

Required:

    master_category_pk UUID PRIMARY KEY

---

## 6.3 Logical Business Attributes

The table requires a stable representation of:

    Category Code
    Category Name
    Description
    Active State

The exact physical column names and lengths are subject to final SQL
approval.

---

## 6.4 Category Code

A category code should provide a stable machine-readable identifier.

Examples from the approved database planning include:

    GENDER
    RELATIONSHIP_TYPE
    MEMBERSHIP_TYPE
    MEMBERSHIP_STATUS
    LOGIN_ROLE
    STATUS_REASON
    WORKFLOW_STATUS
    DOCUMENT_TYPE
    APPLICATION_TYPE

---

## 6.5 Category Uniqueness

Category codes shall be unique.

No two active categories shall represent the same category code.

---

## 6.6 Category Lifecycle

A category that has already been used by business data should not be
physically deleted merely because it is no longer used for new records.

---

# 7. `master_data`

## 7.1 Purpose

Stores reusable values belonging to a master category.

Relationship:

    master_category
          1
          │
          N
          ▼
    master_data

---

## 7.2 Primary Key

Required:

    master_data_pk UUID PRIMARY KEY

---

## 7.3 Foreign Key

Required logical relationship:

    master_data.master_category_pk
              ↓
    master_category.master_category_pk

---

## 7.4 Logical Business Attributes

The table requires a stable representation of:

    Master Category
    Value Code
    Value / Display Name
    Description
    Ordering / Display Sequence
    Active State

The exact physical column catalogue remains subject to final SQL approval.

---

## 7.5 Value Code

Where a master category uses codes, each code shall be stable within that
category.

---

## 7.6 Value Uniqueness

The logical uniqueness requirement is:

    master_category + value_code

A duplicate value code within the same category shall not be permitted.

---

## 7.7 Category Dependency

A master value cannot exist without a valid master category.

---

## 7.8 Inactive Values

An inactive master value shall not normally be selectable for new business
transactions.

Historical records may continue to reference it.

---

# 8. Master Data Design Example

Conceptually:

```text
master_category
----------------
GENDER
   │
   ├── MALE
   ├── FEMALE
   └── OTHER
```

The exact approved master catalogue is maintained separately.

This document defines the table mechanism, not the complete business-value
catalogue.

---

# 9. Generic Master Boundary

The generic master mechanism must not become a dumping ground for every
possible application constant.

The owning business module determines whether a value should be:

```
Generic Master
Domain Master
Configuration
Database Constraint
Application Constant
```

---

# 10. `system_setting`

## 10.1 Purpose

Stores centrally managed configurable system settings.

The source identifies examples including:

```
PASSWORD_EXPIRY_DAYS
MAX_LOGIN_ATTEMPTS
CURRENT_MEMBERSHIP_YEAR
DEFAULT_COUNTRY
PRESIDENT_APPROVAL_REQUIRED
```

These examples demonstrate the intended concept; they are not a final
mandatory seed catalogue.

---

## 10.2 Primary Key

Required:

```
system_setting_pk UUID PRIMARY KEY
```

---

## 10.3 Logical Business Attributes

The table requires a stable representation of:

```
Setting Key
Setting Value
Description
Data Type / Interpretation
Active State
```

The exact physical value representation is not frozen by the current source.

---

## 10.4 Setting Key

A system-setting key shall be unique.

Example:

```
CURRENT_MEMBERSHIP_YEAR
```

shall identify one logical setting.

---

## 10.5 Setting Value

The current source does not freeze whether the value is represented as:

```
VARCHAR
JSON
Separate typed columns
```

Therefore the final physical representation remains pending.

---

## 10.6 Configuration Security

Sensitive configuration values shall not be exposed through ordinary
public/member-facing APIs.

---

## 10.7 Configuration Audit

Important setting changes shall remain auditable through the common Audit
framework.

---

## 10.8 Configuration Lifecycle

A setting may become inactive where the setting is no longer applicable.

Historical configuration changes must remain traceable where required.

---

# 11. `id_sequence_master`

## 11.1 Purpose

Provides centralized sequence infrastructure for business identifiers.

The source explicitly includes this table in Foundation.

---

## 11.2 Primary Key

Required:

```
id_sequence_master_pk UUID PRIMARY KEY
```

---

## 11.3 Logical Business Attributes

The sequence configuration requires a representation of concepts such as:

```
Sequence Name / Code
Current / Next Sequence State
Prefix
Padding / Number Format
Active State
```

The exact physical columns are not completely frozen by the source.

---

## 11.4 Sequence Ownership

Each business identifier sequence shall have one authoritative sequence
definition.

---

## 11.5 Sequence Scope

A sequence definition shall correspond to one defined business identifier
space.

---

## 11.6 Sequence Uniqueness

The sequence identifier/code shall be unique.

---

## 11.7 Permanent IDs

Where an owning business module declares an identifier permanent, sequence
configuration shall not allow accidental reuse of retired identifiers.

---

## 11.8 Concurrent Generation

The final PostgreSQL implementation must guarantee safe concurrent identifier
generation.

The exact mechanism is an implementation/DDL decision.

---

## 11.9 Manual Reset

No unrestricted manual reset of a production business sequence shall be
permitted.

Any approved reset procedure must preserve identifier uniqueness and
historical integrity.

---

# 12. Business ID Ownership

`id_sequence_master` provides sequence infrastructure.

It does not determine the business meaning of an identifier.

For example:

```
Person → owns Person ID rules
Membership → owns Sangha Sevi ID rules
```

Foundation provides the common sequence mechanism where required.

---

# 13. `country`

## 13.1 Purpose

Provides the common country reference master.

---

## 13.2 Primary Key

Required:

```
country_pk UUID PRIMARY KEY
```

---

## 13.3 Logical Business Attributes

The country table requires a representation of:

```
Country Code
Country Name
Active State
```

The exact physical column definition follows the final location-master
design.

---

## 13.4 Country Code

The project has previously established ISO-oriented country-code usage.

The code shall be stable.

---

## 13.5 Country Uniqueness

Country codes shall be unique.

Country names should not be duplicated where they represent the same
country.

---

# 14. `state`

## 14.1 Purpose

Provides state/province geographic reference data.

---

## 14.2 Primary Key

Required:

```
state_pk UUID PRIMARY KEY
```

---

## 14.3 Parent Relationship

Required logical relationship:

```
state
  ↓
country
```

Conceptually:

```
country_pk
    ↑
state.country_pk
```

---

## 14.4 Logical Business Attributes

The table requires:

```
State/Province Code
State/Province Name
Country
Active State
```

Exact physical column names remain subject to final SQL approval.

---

## 14.5 State Uniqueness

A state/province code should be unique within its country.

Logical uniqueness:

```
country + state_code
```

---

# 15. `district`

## 15.1 Purpose

Provides district-level geographic reference data.

---

## 15.2 Primary Key

Required:

```
district_pk UUID PRIMARY KEY
```

---

## 15.3 Parent Relationship

Required logical relationship:

```
district
    ↓
state
```

Conceptually:

```
state_pk
   ↑
district.state_pk
```

---

## 15.4 Logical Business Attributes

The table requires:

```
District Code
District Name
State
Active State
```

Exact physical columns remain subject to final SQL approval.

---

## 15.5 District Uniqueness

A district code should be unique within its state.

Logical uniqueness:

```
state + district_code
```

---

# 16. `city_village`

## 16.1 Purpose

Provides city/village/locality reference data.

---

## 16.2 Primary Key

Required:

```
city_village_pk UUID PRIMARY KEY
```

---

## 16.3 Parent Relationship

Required logical relationship:

```
city_village
     ↓
district
```

Conceptually:

```
district_pk
    ↑
city_village.district_pk
```

---

## 16.4 Logical Business Attributes

The table requires:

```
City/Village Code
City/Village Name
District
Locality Type
Active State
```

The exact physical column definition remains pending final location design.

---

## 16.5 City/Village Uniqueness

The final design shall prevent duplicate geographic records representing the
same locality within the same parent context.

---

# 17. Geographic Hierarchy

The final logical relationship is:

```text
country
   │
   └──< state
           │
           └──< district
                    │
                    └──< city_village
```

---

# 18. Geographic Foreign Keys

The expected foreign keys are:

```text
state.country_pk
        →
country.country_pk

district.state_pk
        →
state.state_pk

city_village.district_pk
        →
district.district_pk
```

---

# 19. Geographic Referential Integrity

A child geographic record shall not reference a nonexistent parent.

Examples:

```
State → valid Country
District → valid State
City/Village → valid District
```

---

# 20. Geographic Hierarchy Is Not Organization

The Foundation location hierarchy shall never be used as a replacement for
the Organization hierarchy.

Geography:

```
Country
State
District
City/Village
```

Organization:

```
Kendra
Anchalika
Zilla
Sakha
```

These remain separate models.

---

# 21. Geographic Lifecycle

Geographic records that have been referenced by historical business data
should not be physically deleted merely to remove them from future
selection.

The final inactive/retired lifecycle must be defined in the location
implementation.

---

# 22. Audit Columns

Where applicable, Foundation tables should include the project-standard
audit metadata:

```
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk

is_active
```

The project source explicitly recommends these audit fields for major
tables.

---

# 23. Audit FK Consideration

Where:

```
created_by_sangha_sevi_pk
updated_by_sangha_sevi_pk
deleted_by_sangha_sevi_pk
```

are implemented as foreign keys, they must reference the authoritative
membership identity according to the final cross-module database
architecture.

The exact FK timing must avoid circular creation dependencies.

---

# 24. Soft Delete

Applicable Foundation reference records shall use the project soft-delete
principle.

Conceptually:

```
is_active = FALSE
deleted_at = timestamp
```

rather than uncontrolled physical deletion.

---

# 25. Historical Reference Preservation

If a historical record references a master/geographic value that becomes
inactive, the historical record must remain interpretable.

---

# 26. Foreign-Key Delete Behaviour

The final DDL shall explicitly define delete behaviour.

For shared reference data, cascading deletion must not destroy dependent
historical records.

The exact `ON DELETE` strategy is finalized in SQL implementation.

---

# 27. Indexing

The following logical access paths should be indexed:

```
master_data → master_category
state → country
district → state
city_village → district
```

Unique business codes should also receive appropriate indexes through their
unique constraints.

---

# 28. Search Support

Geographic names and commonly searched master values may require optimized
search indexes.

The project architecture includes PostgreSQL search-related extensions such
as:

```
pg_trgm
btree_gin
```

The exact indexes are implementation decisions.

---

# 29. Seed Data

The database build plan identifies initial generic master categories:

```
GENDER
RELATIONSHIP_TYPE
MEMBERSHIP_TYPE
MEMBERSHIP_STATUS
LOGIN_ROLE
STATUS_REASON
WORKFLOW_STATUS
DOCUMENT_TYPE
APPLICATION_TYPE
```

These constitute the source-supported seed candidates.

Additional seed data requires approval.

---

# 30. Country Seed Data

The project has previously established common country seed data including:

```
IN — India
US — United States
GB — United Kingdom
AU — Australia
CA — Canada
```

These seed values belong to the Foundation location master.

---

# 31. Master Category Seed Governance

Seed categories shall not be duplicated across modules.

If a category already exists in Foundation, consuming modules should use it
rather than create an equivalent category.

---

# 32. Table-Level Ownership

| Table                | Foundation Responsibility          |
| -------------------- | ---------------------------------- |
| `master_category`    | Generic category mechanism         |
| `master_data`        | Generic value mechanism            |
| `system_setting`     | Configuration storage              |
| `id_sequence_master` | Identifier sequence infrastructure |
| `country`            | Country reference                  |
| `state`              | State/province reference           |
| `district`           | District reference                 |
| `city_village`       | Locality reference                 |

---

# 33. Tables Not Added

The Foundation table design does not introduce:

```
organization
person
family_group
user_account
role_master
permission_master
audit_master
notification
document_store
```

Those belong to other modules/capabilities.

---

# 34. No Duplicate Location Model

The following generic tables shall not be independently recreated in
business modules:

```
country
state
district
city_village
```

---

# 35. No Generic Transaction Model

Foundation does not contain business transactions.

For example:

```
Membership Renewal
Attendance
Election
Publication Purchase
Sevak Assignment
```

remain outside Foundation.

---

# 36. Data-Type Boundary

The current source does not provide authoritative lengths for:

```
codes
names
descriptions
setting values
```

Therefore exact `VARCHAR(n)` lengths shall not be treated as frozen by this
document.

They must be finalized before DDL generation.

---

# 37. Required Finalization Before SQL

Before generating PostgreSQL DDL, the following remain to be explicitly
confirmed:

```
Exact column names
Exact VARCHAR lengths
Exact NULL/NOT NULL rules
Exact audit-column applicability
Exact setting value representation
Exact sequence implementation
Exact geographic code structure
Exact city/village type representation
Exact delete behaviour
Exact indexes
Exact seed-data catalogue
```

---

# 38. Database-First Rule

No SQL should be generated from assumptions that are not supported by the
Foundation design.

The correct sequence remains:

```
Business Rules
      ↓
ERD
      ↓
Table Design
      ↓
PostgreSQL DDL
```

---

# 39. Final Logical Schema

```text
MASTER DATA

master_category
      │
      └──< master_data


CONFIGURATION

system_setting


IDENTIFIER INFRASTRUCTURE

id_sequence_master


GEOGRAPHY

country
   │
   └──< state
           │
           └──< district
                    │
                    └──< city_village


SHARED INFRASTRUCTURE (added 2026-08-26)

document_master     (shared document registry — DOC-ARCH-001)
field_change_log    (shared field-change tracking — Data Change Architecture)
```

---

# 40. Foundation Table Count

Current count:

```
10 tables
```

```text
1. master_category
2. master_data
3. system_setting
4. id_sequence_master
5. country
6. state
7. district
8. city_village
9. document_master        (DOC-ARCH-001, 2026-08-26)
10. field_change_log      (Data Change Architecture, 2026-08-26)
```

---

# 41. Source Alignment

The source database review identifies the original eight Foundation tables and
explicitly separates them from Person, Membership, Authentication,
Organization, Governance and other modules.

Two additional tables (`document_master`, `field_change_log`) were assigned
to Foundation by architectural decisions made during the pre-DB architecture
gate (2026-08-26). Their logical column designs are defined by Person
(for `document_master`) and the Data Change Architecture (for
`field_change_log`); Foundation owns the physical DDL.

The database build plan confirms:

```
master_category
master_data
```

as the generic master framework, provides system-setting examples, and
groups:

```
country
state
district
city_village
```

as the geographic Foundation.

The project-wide database standards establish UUID technical PKs, the
`<table_name>_pk` naming convention, business-ID separation, audit metadata,
and soft-delete principles.

---

# 42. Status

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
