# NSS ERP — Foundation Business Rules

**Document ID:** SOL-FND-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Foundation
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the common Foundation
layer of NSS ERP.

Foundation provides:

    Master Data
    System Settings
    Identifier Sequence Management
    Geographic Reference Data

Foundation is a shared dependency and shall not absorb ownership of
business-domain rules belonging to other modules.

---

# 2. Rule Classification

Rules are classified as:

- FROZEN — explicitly established by project source
- SOURCE-ALIGNED — supported by existing project architecture
- PENDING — requires further approval
- FUTURE — outside current frozen scope

---

# 3. Foundation Architecture

## FND-BR-001 — Common Foundation Layer

**Status:** FROZEN

Foundation shall provide common capabilities used by multiple ERP modules.

---

## FND-BR-002 — No Duplicate Common Infrastructure

**Status:** FROZEN

A business module shall not independently recreate a common Foundation
capability where an approved Foundation capability already exists.

Examples:

    Geographic Masters
    Generic Master Data
    ID Sequence Infrastructure
    Common System Settings

---

## FND-BR-003 — Foundation Does Not Own Business Domains

**Status:** FROZEN

Foundation shall not become the owner of:

    Person
    Membership
    Organization
    Governance
    Attendance
    Family
    Sevak
    UPBS
    Heritage
    Reports

Those remain separate business domains.

---

# 4. Master Data

## FND-BR-004 — Master Data Driven Architecture

**Status:** FROZEN

NSS ERP shall follow a Master Data Driven architecture.

Common controlled values should be maintained centrally and reused by
consuming modules.

---

## FND-BR-005 — Generic Master Framework

**Status:** FROZEN

The generic master-data framework consists of:

    master_category
    master_data

The source identifies this as the generic master framework.

---

## FND-BR-006 — Master Category

**Status:** SOURCE-ALIGNED

A `master_category` identifies a logical group of related master values.

Examples may include:

    GENDER
    RELATIONSHIP_TYPE
    MEMBERSHIP_TYPE
    MEMBERSHIP_STATUS
    DOCUMENT_TYPE
    WORKFLOW_STATUS

The authoritative Master Data Catalog determines the approved categories.

---

## FND-BR-007 — Master Data Belongs to a Category

**Status:** SOURCE-ALIGNED

A generic master value shall belong to its applicable master category.

Conceptually:

    master_category
          ↓
    master_data

---

## FND-BR-008 — No Uncontrolled Master Values

**Status:** SOURCE-ALIGNED

Business modules shall not introduce arbitrary generic master values without
following the approved master-data governance process.

---

## FND-BR-009 — Stable Master Codes

**Status:** SOURCE-ALIGNED

Where a master value has a business code, the code shall remain stable after
the value is introduced.

Changing a display label should not silently change the underlying business
meaning.

---

## FND-BR-010 — Master Value Uniqueness

**Status:** SOURCE-ALIGNED

Duplicate values/codes within the same master category shall not be created
where the category requires uniqueness.

---

# 5. Master Data Ownership

## FND-BR-011 — Foundation Owns the Mechanism

**Status:** FROZEN

Foundation owns the generic master-data mechanism.

The business module owns the domain meaning of the master.

---

## FND-BR-012 — Domain Ownership Remains Separate

**Status:** FROZEN

Foundation shall not redefine a business rule merely because the business
domain uses a Foundation master.

Example:

    Foundation → provides master-data mechanism

    Membership → owns membership rules

    Governance → owns governance rules

---

## FND-BR-013 — One Authoritative Common Value

**Status:** SOURCE-ALIGNED

Where the same business concept is genuinely common across modules, the ERP
should maintain one authoritative representation.

---

# 6. Master Value Lifecycle

## FND-BR-014 — Master Values May Become Inactive

**Status:** SOURCE-ALIGNED

A master value may be made inactive when it is no longer valid for future
use.

---

## FND-BR-015 — Inactive Values Preserve History

**Status:** FROZEN

Making a master value inactive shall not invalidate historical records that
previously used that value.

---

## FND-BR-016 — No Casual Physical Deletion

**Status:** FROZEN

A master value shall not be physically deleted when doing so would destroy
historical integrity.

---

# 7. Master Data vs Configuration

## FND-BR-017 — Master Data and Settings Are Different

**Status:** FROZEN

The system shall distinguish:

    Master Data
    System Settings

Master Data represents reusable reference values.

System Settings represent configurable system behaviour or parameters.

---

# 8. System Settings

## FND-BR-018 — Central System Configuration

**Status:** FROZEN

System-wide configurable settings shall be centrally managed through:

    system_setting

---

## FND-BR-019 — Configuration Over Hardcoding

**Status:** FROZEN

Where a system behaviour is intentionally configurable, the value should be
managed through configuration rather than scattered hard-coded constants.

This is an established project architecture principle.

---

## FND-BR-020 — Configuration Cannot Override Frozen Rules

**Status:** FROZEN

A system setting shall not be used to override:

    Constitution
    Bye-Laws
    Authoritative References
    Frozen Business Rules
    Governance Decisions

---

## FND-BR-021 — Controlled Configuration

**Status:** SOURCE-ALIGNED

System settings shall be changed only through authorized administrative
operations.

---

## FND-BR-022 — Configuration Auditability

**Status:** SOURCE-ALIGNED

Significant system-setting changes should remain auditable through the
common Audit framework.

---

# 9. System Setting Values

## FND-BR-023 — Setting Type

**Status:** PENDING

The current source does not freeze the complete physical representation of
setting values.

Possible implementation approaches include:

    String
    Numeric
    Boolean
    Date
    JSON

The final column-level design will be decided in Table Design.

---

## FND-BR-024 — Setting Catalogue

**Status:** PENDING

The complete list of system settings is not frozen.

Examples previously discussed include:

    PASSWORD_EXPIRY_DAYS
    MAX_LOGIN_ATTEMPTS
    CURRENT_MEMBERSHIP_YEAR
    DEFAULT_COUNTRY
    PRESIDENT_APPROVAL_REQUIRED

These are examples, not a final frozen catalogue.

---

# 10. Identifier Sequences

## FND-BR-025 — Central Identifier Infrastructure

**Status:** FROZEN

Foundation shall provide centralized identifier-sequence infrastructure
through:

    id_sequence_master

---

## FND-BR-026 — One Sequence Owner

**Status:** FROZEN

Each business identifier sequence shall have one authoritative sequence
definition.

Two modules shall not independently generate identifiers from the same
business identifier space.

---

## FND-BR-027 — Technical PK vs Business ID

**Status:** FROZEN

The system shall distinguish:

    Technical Primary Key
    Business Identifier

Technical PKs identify database records.

Business IDs identify business entities according to domain rules.

---

## FND-BR-028 — Business ID Ownership

**Status:** FROZEN

The business module owning an entity determines the business-ID rules.

Foundation provides the common sequence infrastructure where required.

---

## FND-BR-029 — Permanent Business IDs

**Status:** SOURCE-ALIGNED

Where a business domain declares its identifier permanent, Foundation shall
support generation without reuse.

Foundation itself does not decide whether a business ID is permanent.

---

## FND-BR-030 — Identifier Reuse

**Status:** FROZEN

A permanent business identifier shall not be reused after retirement.

---

## FND-BR-031 — Sequence Concurrency

**Status:** SOURCE-ALIGNED

Identifier generation must prevent duplicate identifiers under concurrent
requests.

The exact PostgreSQL sequence/locking implementation belongs to SQL design.

---

## FND-BR-032 — Manual Identifier Assignment

**Status:** PENDING

The current source does not freeze whether authorized administrators may
manually assign business identifiers.

If permitted, the process must preserve uniqueness and sequence integrity.

---

# 11. Geographic Masters

## FND-BR-033 — Common Geographic Reference

**Status:** FROZEN

Foundation shall provide common geographic reference data.

Current tables:

    country
    state
    district
    city_village

---

## FND-BR-034 — Geographic Hierarchy

**Status:** SOURCE-ALIGNED

The logical geographic hierarchy is:

    Country
       ↓
    State
       ↓
    District
       ↓
    City/Village

---

## FND-BR-035 — Valid Parent Relationship

**Status:** SOURCE-ALIGNED

Every geographic child record must reference a valid parent at the
appropriate level.

Examples:

    State → Country
    District → State
    City/Village → District

---

## FND-BR-036 — No Orphan Geographic Records

**Status:** FROZEN

The geographic hierarchy shall not contain orphan records where a valid
parent is required.

---

## FND-BR-037 — Geographic Integrity

**Status:** SOURCE-ALIGNED

Geographic relationships shall remain structurally valid throughout their
lifecycle.

---

# 12. Geographic vs Organization

## FND-BR-038 — Separate Geographic and Organizational Hierarchies

**Status:** FROZEN

Geographic hierarchy and NSS organizational hierarchy are separate concepts.

Geographic:

    Country
       ↓
    State
       ↓
    District
       ↓
    City/Village

NSS Organization:

    Kendra
       ↓
    Anchalika
       ↓
    Zilla
       ↓
    Sakha

They shall not be merged.

---

## FND-BR-039 — City/Village Is Not Sakha

**Status:** FROZEN

A city or village is geographic data.

A Sakha is an NSS organizational entity.

One shall not be treated as the other.

---

# 13. Geographic Reuse

## FND-BR-040 — Shared Geographic Masters

**Status:** FROZEN

Business modules requiring geographic reference data should use the common
Foundation geographic masters.

---

## FND-BR-041 — No Duplicate Geographic Tables

**Status:** FROZEN

Business modules shall not create duplicate generic:

    country
    state
    district
    city/village

tables.

---

# 14. Geographic Lifecycle

## FND-BR-042 — Historical Location Integrity

**Status:** SOURCE-ALIGNED

Changes to geographic reference data shall not casually invalidate
historical records.

---

## FND-BR-043 — Geographic Deactivation

**Status:** PENDING

The exact policy for deactivating or retiring geographic records requires
final location-master design.

---

## FND-BR-044 — Geographic Merging

**Status:** PENDING

The current source does not freeze a detailed workflow for merging or
renaming geographic entities.

---

# 15. Foundation and Organization

## FND-BR-045 — Organization Owns Organizational Hierarchy

**Status:** FROZEN

The Organization Module remains authoritative for NSS organizational
structure.

Foundation does not own:

    Kendra
    Anchalika
    Zilla
    Sakha

as organizational entities.

---

## FND-BR-046 — Foundation May Support Organization

**Status:** SOURCE-ALIGNED

Organization may use Foundation geographic and master data.

This does not transfer organizational ownership to Foundation.

---

# 16. Foundation and Person

## FND-BR-047 — Person Owns Person Identity

**Status:** FROZEN

Foundation does not own Person identity.

Person remains the authoritative domain for personal information.

---

## FND-BR-048 — Person May Consume Foundation Masters

**Status:** SOURCE-ALIGNED

Person may reference Foundation masters such as:

    Gender
    Blood Group
    Geographic Data

where those values are approved as common masters.

---

# 17. Foundation and Membership

## FND-BR-049 — Membership Owns Membership Rules

**Status:** FROZEN

Foundation does not own:

    Membership Type Rules
    Membership Status Rules
    Renewal Rules
    Transfer Rules
    Probationary Progression

Membership remains authoritative for those rules.

---

## FND-BR-050 — Membership May Consume Foundation Masters

**Status:** SOURCE-ALIGNED

Membership may consume approved Foundation master-data infrastructure.

---

# 18. Foundation and Governance

## FND-BR-051 — Governance Owns Governance Rules

**Status:** FROZEN

Foundation does not own:

    Governing Bodies
    Positions
    Elections
    Governance Authority

Those belong to Governance.

---

# 19. Foundation and Authentication

## FND-BR-052 — Authentication Is Separate

**Status:** FROZEN

Foundation does not own:

    Authentication
    Passwords
    JWT
    Sessions
    Roles
    Permissions

These belong to Authentication & Security / Administration.

---

# 20. Foundation and Audit

## FND-BR-053 — Central Audit Framework

**Status:** FROZEN

Foundation shall use the common Audit framework where Foundation changes
require auditability.

It shall not create a duplicate audit system.

---

# 21. Foundation and Security

## FND-BR-054 — Central RBAC

**Status:** FROZEN

Administrative access to Foundation operations shall use the centralized ERP
RBAC framework.

Foundation shall not create its own permission system.

---

## FND-BR-055 — Scope-Aware Administration

**Status:** SOURCE-ALIGNED

Where Foundation administration is organizationally scoped, access shall
respect the centralized organizational-scope model.

---

# 22. Master Data Governance

## FND-BR-056 — Approved Master Creation

**Status:** SOURCE-ALIGNED

New master categories and values shall be introduced through the approved
project governance/change process.

---

## FND-BR-057 — No UI-Driven Master Creation

**Status:** SOURCE-ALIGNED

A UI requirement alone shall not justify creating a new master category.

The underlying business requirement must be established first.

---

## FND-BR-058 — Master Catalogue Authority

**Status:** FROZEN

The project's Master Data Catalog is the authoritative documentation source
for approved master categories and values.

---

# 23. Master Values vs Enumerations

## FND-BR-059 — Controlled Value Strategy

**Status:** SOURCE-ALIGNED

The project shall deliberately distinguish between:

    Database-enforced technical constants
    Master-data-driven business values
    Configurable system settings

Not every value should automatically become a generic master.

---

# 24. History

## FND-BR-060 — History Never Deleted

**Status:** FROZEN

The project follows the principle:

    History Never Deleted

where historical preservation is required.

---

## FND-BR-061 — Historical Master References

**Status:** FROZEN

Historical records must remain interpretable even when a master value later
becomes inactive.

---

# 25. Soft Delete

## FND-BR-062 — Soft Delete Where Applicable

**Status:** SOURCE-ALIGNED

Applicable Foundation records shall follow the project-wide soft-delete
standard rather than uncontrolled physical deletion.

Standard lifecycle concepts include:

    is_active
    deleted_at
    deleted_by_sangha_sevi_pk

---

# 26. Data Quality

## FND-BR-063 — No Duplicate Common Reference

**Status:** SOURCE-ALIGNED

The Foundation layer should prevent duplicate common reference values where
uniqueness is required.

---

## FND-BR-064 — Valid Parent References

**Status:** SOURCE-ALIGNED

Parent-child master relationships must always reference valid parent
records.

---

# 27. Configuration Safety

## FND-BR-065 — Configuration Must Be Validated

**Status:** SOURCE-ALIGNED

Configurable values must be validated according to their intended data
type and business meaning.

---

## FND-BR-066 — Configuration Cannot Create Authority

**Status:** FROZEN

A system setting shall not be used to create governance authority,
organizational authority, or membership rights that do not otherwise exist.

---

# 28. Identifier Safety

## FND-BR-067 — Identifier Uniqueness

**Status:** FROZEN

Generated business identifiers must remain unique within their defined
identifier space.

---

## FND-BR-068 — Identifier Stability

**Status:** FROZEN

Once issued, a permanent business identifier shall remain associated with
the entity for which it was issued.

---

# 29. Foundation Data Changes

## FND-BR-069 — Controlled Change

**Status:** SOURCE-ALIGNED

Changes to shared Foundation data must be evaluated for downstream impact
before implementation.

Because Foundation is shared, a seemingly small change may affect multiple
modules.

---

## FND-BR-070 — Backward Compatibility

**Status:** SOURCE-ALIGNED

Changes to common master values, system settings, or geographic data should
preserve compatibility with historical and active consuming modules where
possible.

---

# 30. Seed Data

## FND-BR-071 — Approved Seed Data

**Status:** SOURCE-ALIGNED

Seed data shall come from approved project master-data definitions.

Unapproved arbitrary seed values shall not be introduced merely for
development convenience.

---

# 31. International Geography

## FND-BR-072 — Country Support

**Status:** SOURCE-ALIGNED

The geographic foundation should support countries beyond India where the
ERP requirements require them.

The project has previously established ISO-oriented country-code usage.

---

## FND-BR-073 — India-Specific Geography

**Status:** SOURCE-ALIGNED

Indian state/district/locality data may use the approved Indian geographic
reference structure.

India-specific assumptions shall not prevent valid international country
records where international support is required.

---

# 32. Foundation API Boundary

## FND-BR-074 — API Authorization

**Status:** SOURCE-ALIGNED

Foundation APIs shall enforce authentication and applicable authorization.

---

## FND-BR-075 — API Does Not Bypass Database Integrity

**Status:** SOURCE-ALIGNED

APIs shall respect the database's referential and uniqueness constraints.

---

# 33. Foundation UI Boundary

## FND-BR-076 — UI Is Not Security Boundary

**Status:** SOURCE-ALIGNED

Hiding a master-data or configuration function in the UI does not constitute
authorization.

Backend/API enforcement remains mandatory.

---

# 34. Reporting Dependency

## FND-BR-077 — Reports Use Authoritative Foundation Data

**Status:** SOURCE-ALIGNED

Reports should use the authoritative Foundation masters rather than
maintaining independent reference lists.

---

# 35. Search Dependency

## FND-BR-078 — Common Reference Search

**Status:** SOURCE-ALIGNED

Where common geographic or master data is searchable, the Foundation
representation should remain the authoritative source.

---

# 36. Performance

## FND-BR-079 — Shared Master Data Performance

**Status:** SOURCE-ALIGNED

Frequently accessed common master data should be indexed appropriately.

Exact indexing belongs to Table Design and SQL implementation.

---

# 37. Concurrency

## FND-BR-080 — Concurrent Sequence Safety

**Status:** SOURCE-ALIGNED

Concurrent identifier requests must not result in duplicate business
identifiers.

The exact PostgreSQL implementation belongs to DDL/implementation.

---

# 38. Current Frozen Tables

## FND-BR-081 — Foundation Table Set

**Status:** FROZEN

The current Foundation table set is exactly:

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

# 39. Tables Not Introduced

## FND-BR-082 — No Unapproved Foundation Tables

**Status:** FROZEN

The following are not part of the current Foundation schema:

    person
    family_group
    user_account
    role_master
    permission_master
    audit_master
    system_event_log
    organization
    notification
    document_store

These belong to other modules/capabilities.

---

# 40. Foundation Governance

## FND-BR-083 — Governance Change Control

**Status:** SOURCE-ALIGNED

Changes to shared Foundation architecture shall follow the project's
governance and change-control process.

---

## FND-BR-084 — Authoritative References

**Status:** FROZEN

Where a Foundation-related rule derives from an authoritative source, that
source takes precedence over informal implementation assumptions.

---

# 41. Rule Summary

| Area | Status |
|---|---|
| Common Foundation Layer | FROZEN |
| No Duplicate Infrastructure | FROZEN |
| Master Data Driven | FROZEN |
| Generic Master Framework | FROZEN |
| Central System Settings | FROZEN |
| Configuration Over Hardcoding | FROZEN |
| Central ID Sequence | FROZEN |
| Technical PK ≠ Business ID | FROZEN |
| Permanent IDs Not Reused | FROZEN |
| Common Geographic Masters | FROZEN |
| Geographic Hierarchy | SOURCE-ALIGNED |
| No Geographic Duplication | FROZEN |
| Geographic ≠ Organization | FROZEN |
| History Never Deleted | FROZEN |
| Soft Delete | SOURCE-ALIGNED |
| Central RBAC | FROZEN |
| Central Audit | FROZEN |
| Master Catalogue Authority | FROZEN |
| Manual ID Assignment | PENDING |
| System Setting Value Types | PENDING |
| Complete System Setting Catalogue | PENDING |
| Geographic Deactivation | PENDING |
| Geographic Merge Workflow | PENDING |

---

# 42. Core Foundation Principle

The Foundation Module shall provide:

    Common Reference Data
    Common Configuration
    Common Identifier Infrastructure
    Common Geographic Reference

without taking ownership of business-domain rules.

---

# 43. Architectural Model

```text
                    FOUNDATION
                        │
       ┌────────────────┼─────────────────┐
       │                │                 │
       ▼                ▼                 ▼
  Master Data      System Settings    ID Sequences
       │                                  │
       │                                  │
       └──────────────┬───────────────────┘
                      │
                      ▼
               Shared ERP Layer

                  GEOGRAPHY
                      │
                      ▼
             Country → State
                      ↓
                  District
                      ↓
               City/Village
```

---

# 44. Source Alignment

The project source establishes the Foundation as the common layer and
identifies the eight Foundation tables:

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

The project database build plan identifies the corresponding Foundation
implementation areas:

```
03_master_tables.sql
04_system_setting.sql
05_id_sequence_master.sql
06_geo_tables.sql
```

and establishes the generic master framework and geographic foundation.

The project architecture also explicitly establishes:

```
Master Data Driven
Configuration Over Hardcoding
History Never Deleted
By-Law Supremacy
Documentation First
```

as core project principles.

---

# 45. Status

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
