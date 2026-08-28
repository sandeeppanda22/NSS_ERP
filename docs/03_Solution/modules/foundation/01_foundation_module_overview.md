# NSS ERP — Foundation Module Overview

**Document ID:** SOL-FND-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Foundation
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Foundation Module provides the common technical and business foundation
used by the other NSS ERP modules.

It contains shared infrastructure and common master-data capabilities that
must remain consistent across the ERP.

The Foundation Module is not a business-operation module.

It provides reusable platform capabilities for other modules.

---

# 2. Core Principle

The Foundation Module follows:

    Configure Once
          ↓
    Reuse Everywhere

Common values, system configuration, identifiers, and foundational
reference data shall not be independently recreated inside individual
business modules.

---

# 3. Foundation Role in NSS ERP

The Foundation Module sits beneath the major business modules.

Conceptually:

```text
                         Foundation
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
     Person              Organization          Membership
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                     Other Business Modules
```

Foundation provides common capabilities and reference data consumed by
these modules.

---

# 4. Foundation vs Business Modules

The Foundation Module is different from modules such as:

    Person
    Organization
    Membership
    Family
    Attendance
    Governance
    Sevak
    UPBS
    Heritage
    Reports

Those modules implement domain-specific functionality.

Foundation provides shared infrastructure and master-data capabilities.

---

# 5. Foundation vs Organization

Foundation is NOT the Organization Module.

## Foundation

Responsible for:

    Master Data
    System Settings
    ID Sequences
    Common Geographic Reference Data

## Organization

Responsible for:

    NSS Organizational Structure
    Organizational Units
    Organizational Hierarchy
    Sakha and related organizational entities

Foundation may provide master/reference infrastructure used by Organization,
but it does not own the statutory organizational hierarchy.

---

# 6. Foundation vs Person

Foundation is NOT the Person Module.

Person owns:

    Person Identity
    Personal Information
    Person Lifecycle

Foundation provides common reference/master infrastructure consumed by
Person.

---

# 7. Foundation Module Scope

The current source identifies the Foundation database foundation as:

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

This is the current source-supported Foundation table set.

---

# 8. Core Foundation Components

The Foundation Module consists of four major areas:

## 8.1 Master Data

    master_category
    master_data

## 8.2 System Configuration

    system_setting

## 8.3 Identifier Generation

    id_sequence_master

## 8.4 Geographic Reference Data

    country
    state
    district
    city_village

---

# 9. Master Data

The Foundation Module provides centralized master-data management.

The objective is to avoid hard-coded business values throughout the
application.

Conceptually:

    Master Category
          ↓
    Master Data
          ↓
    Business Modules

---

# 10. Master Category

`master_category` represents a logical category of configurable/master
values.

Examples may include categories such as:

    Membership Status
    Event Type
    Publication Type
    Language
    Other Approved Masters

The final catalogue is governed by the Master Data Catalog.

---

# 11. Master Data

`master_data` contains configurable values belonging to approved master
categories.

The same master value should be reusable wherever the business meaning is
identical.

---

# 12. Master Data Driven Architecture

The project follows the principle:

    Master Data Driven

Business modules should consume approved master values rather than creating
duplicate hard-coded enumerations.

The source explicitly identifies Master Data Driven architecture as a
project principle.

---

# 13. Master Data Ownership

Foundation owns the generic master-data mechanism.

A business module remains responsible for defining the business meaning of
its domain.

For example:

    Foundation
        → provides master-data mechanism

    Membership
        → defines membership-related business concepts

    Governance
        → defines governance-related business concepts

Foundation shall not silently redefine business rules owned by another
module.

---

# 14. System Settings

`system_setting` provides centrally managed configurable system values.

The purpose is to avoid scattering configurable behaviour throughout source
code.

Examples may include:

    System Configuration
    Feature Configuration
    Operational Parameters
    Approved System Defaults

The exact setting catalogue is not frozen by this overview.

---

# 15. Configuration Over Hardcoding

The project follows:

    Configuration Over Hardcoding

where a value is expected to be configurable.

This principle is explicitly part of the project architecture.

---

# 16. System Setting Boundary

System settings shall not be used to override statutory rules or
frozen business rules.

Configuration controls implementation behaviour where configuration is
permitted.

It does not create new business authority.

---

# 17. ID Sequence Management

`id_sequence_master` provides centralized identifier-sequence management.

The purpose is to support controlled generation of business identifiers
without duplicating sequence logic across modules.

---

# 18. Business ID Principle

The project distinguishes:

    Technical Primary Key
    Business Identifier

Example:

    person_pk
    person_id

The technical PK identifies the database record.

The business identifier identifies the record within the business domain.

---

# 19. Identifier Generation

Business identifiers requiring centralized sequencing shall use the approved
ID sequence mechanism.

The Foundation Module owns the common sequence infrastructure.

Individual modules shall not independently implement conflicting sequence
mechanisms for the same identifier domain.

---

# 20. Identifier Permanence

Where a business identifier has been declared permanent by its owning
module, Foundation shall support the requirement that the identifier is not
reused.

Foundation does not independently decide whether an identifier is
permanent; that rule belongs to the owning business domain.

---

# 21. Geographic Reference Data

Foundation provides common geographic reference data:

    country
    state
    district
    city_village

These are shared reference entities.

---

# 22. Geographic Hierarchy

The logical geographic relationship is:

    Country
       ↓
    State
       ↓
    District
       ↓
    City / Village

The final relationship structure follows the approved location master
design.

---

# 23. Geographic Data Reuse

Business modules should reference the common geographic masters rather than
creating duplicate location tables.

Examples include:

    Person Addresses
    Organization Locations
    Event Locations
    Family Locations
    Other Approved Location References

---

# 24. Country Master

`country` provides the common country reference set.

The project has previously established ISO-oriented country-code usage for
the location architecture.

The final physical column definition belongs to the location table design.

---

# 25. State Master

`state` provides state/province reference data under the appropriate
country.

---

# 26. District Master

`district` provides district-level geographic reference data.

---

# 27. City/Village Master

`city_village` provides the lower-level locality reference.

It shall not be confused with an NSS organizational unit.

A city/village is geographic data.

A Sakha is an organizational entity.

---

# 28. Geographic vs Organizational Structure

The Foundation geographic hierarchy:

    Country
       ↓
    State
       ↓
    District
       ↓
    City/Village

is different from the NSS organizational hierarchy:

    Kendra
       ↓
    Anchalika
       ↓
    Zilla
       ↓
    Sakha

They must not be merged into one hierarchy.

---

# 29. Foundation as Shared Dependency

Other modules may depend on Foundation.

Conceptually:

    Foundation
       │
       ├── Person
       ├── Family
       ├── Organization
       ├── Membership
       ├── Attendance
       ├── Governance
       ├── Sevak
       ├── UPBS
       └── Other Modules

The dependency direction should remain controlled.

---

# 30. No Reverse Ownership

A business module shall not become the hidden owner of a common Foundation
master that is intended for system-wide reuse.

---

# 31. Common Data Consistency

A common reference value should have one authoritative representation where
the business meaning is identical.

Duplicate representations create:

    Inconsistent Reporting
    Invalid References
    Data Duplication
    Maintenance Problems

---

# 32. Foundation Does Not Own Business Transactions

Foundation shall not own domain transactions such as:

    Membership Renewal
    Attendance
    Election
    Governance Assignment
    UPBS Registration
    Sevak Activity
    Publication Purchase

Those belong to their respective business modules.

---

# 33. Foundation Does Not Own Reports

Foundation provides reference/configuration data consumed by Reports &
Analytics.

It does not own business reporting logic.

---

# 34. Foundation Does Not Own Audit

The project has a separate Audit capability.

Foundation may be subject to audit requirements but shall not create a
duplicate audit framework.

---

# 35. Foundation Does Not Own Authentication

Authentication & Security is a separate module.

Foundation does not own:

    Login
    Password Authentication
    JWT
    Session Security
    Roles
    Permissions

Those responsibilities belong to Authentication & Security and
Administration/RBAC.

---

# 36. Foundation Does Not Own Notifications

Notification delivery is a separate common capability.

Foundation may provide configurable notification-related master values where
approved, but it does not become the notification engine.

---

# 37. Master Data Governance

Master-data changes must follow the project's governance and change-control
standards.

A new master value should not be introduced merely because a UI requires a
new option.

---

# 38. Master Data vs Configuration

The system distinguishes:

    Master Data
    System Configuration

Master Data represents controlled business/reference values.

System Configuration represents configurable system behaviour.

They shall not be treated as interchangeable.

---

# 39. Master Data vs Business Transaction

Master data defines reusable reference values.

Transactions record actual business activity.

Example:

    Event Type
        → Master Data

    Actual Event
        → Business Transaction

---

# 40. System Setting Governance

System settings shall have controlled ownership.

A setting should not be introduced when the value is actually a fixed
statutory or business rule.

---

# 41. Statutory Rules

Foundation configuration cannot override:

    NSS Bye-Law
    Approved Bye-Laws
    Authoritative References
    Frozen Governance Rules

The governance lifecycle establishes authoritative references as the source
for downstream requirements and solution design.

---

# 42. Auditability

Changes to Foundation configuration and master data should be traceable
where required by the common Audit framework.

Examples:

    Master Value Created
    Master Value Deactivated
    System Setting Changed
    Sequence Configuration Changed
    Geographic Reference Updated

---

# 43. History Preservation

The project follows:

    History Never Deleted

where historical preservation is required.

Foundation changes must therefore preserve historical integrity.

---

# 44. Soft Delete

Applicable Foundation records shall follow the project-wide lifecycle and
soft-delete standards.

The exact applicability is finalized during Table Design.

---

# 45. Inactive Master Values

A master value may become inactive where business requirements permit.

Deactivation should prevent inappropriate future use while preserving
historical references.

---

# 46. Historical References

Historical transactions that used an earlier master value must remain
interpretable after that value becomes inactive.

---

# 47. Geographic Master Changes

Changes to geographic reference data must not casually invalidate historical
addresses or locations.

The final location lifecycle rules shall be established in the location
table design.

---

# 48. ID Sequence Integrity

Identifier generation must avoid:

    Duplicate Business IDs
    Accidental Reuse
    Uncontrolled Reset
    Conflicting Sequence Ownership

---

# 49. Sequence Ownership

Each business identifier sequence shall have one authoritative owner.

Two modules shall not independently generate the same business identifier
space.

---

# 50. Foundation Security

Foundation data shall be protected according to the common ERP security
architecture.

Access to administrative master-data operations shall be controlled through
centralized RBAC.

---

# 51. Foundation RBAC

Foundation does not create its own permission system.

Administrative access uses:

    Authentication
       ↓
    Central RBAC
       ↓
    Organizational Scope
       ↓
    Foundation Operation

---

# 52. API Boundary

Foundation APIs shall expose only approved master/configuration operations.

The API shall enforce:

    Authentication
    Authorization
    Scope

where applicable.

---

# 53. UI Boundary

Foundation master-data screens shall consume the same API/security
architecture as the rest of the ERP.

UI restrictions alone are not authorization.

---

# 54. Data Validation

Foundation shall provide structurally valid reference data to consuming
modules.

Business modules remain responsible for domain-specific validation.

---

# 55. Master Data Naming

Master values shall follow the project naming and coding conventions.

The same concept should not receive multiple codes in different modules
without an approved reason.

---

# 56. Duplicate Master Prevention

Where a master category requires unique values/codes, the database shall
enforce the approved uniqueness rules.

---

# 57. Location Master Integrity

Geographic records shall maintain valid parent-child relationships.

For example:

    District → valid State
    City/Village → valid District

The exact constraints belong to the location Table Design.

---

# 58. Foundation Dependency Model

```text
                  FOUNDATION
                      │
       ┌──────────────┼───────────────┐
       │              │               │
       ▼              ▼               ▼
  Master Data    System Settings   ID Sequences
       │                              │
       │                              │
       └──────────────┬───────────────┘
                      │
                      ▼
              Shared ERP Services

                  LOCATION
                     │
                     ▼
            Shared Geographic Data
```

---

# 59. Current Frozen Table Set

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

This eight-table Foundation classification is confirmed by the project
schema review.

---

# 60. Tables Not Added

The Foundation Module does not introduce:

```
audit_master
system_event_log
user_account
role_master
permission_master
person
organization
family_group
```

These belong to their respective modules/foundation areas.

---

# 61. Module Boundary Summary

| Capability                 | Owner                     |
| -------------------------- | ------------------------- |
| Generic Master Data        | Foundation                |
| System Settings            | Foundation                |
| ID Sequence Infrastructure | Foundation                |
| Geographic Masters         | Foundation                |
| Person Identity            | Person                    |
| Family                     | Family                    |
| Organizational Hierarchy   | Organization              |
| Membership                 | Membership                |
| Authentication             | Authentication & Security |
| RBAC Administration        | Administration            |
| Governance                 | Governance                |
| Audit                      | Audit                     |
| Reporting                  | Reports & Analytics       |

---

# 62. Architecture Principle

The Foundation Module exists to prevent duplication.

Therefore:

```
Common capability
      ↓
Foundation
      ↓
Reused by modules
```

rather than:

```
Common capability
   ├── Person copy
   ├── Membership copy
   ├── Governance copy
   └── UPBS copy
```

---

# 63. Database-First Boundary

Foundation follows the project's design sequence:

```
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
```

This document is only the Module Overview.

No SQL or API design is introduced here.

---

# 64. Future Expansion

Additional common infrastructure may be introduced in future phases if
formally approved.

Examples could include:

```
Additional geographic levels
Common document infrastructure
Common notification infrastructure
Common workflow infrastructure
```

Such capabilities must not be added to Foundation merely for convenience.

---

# 65. Core Foundation Principle

The Foundation Module shall provide:

```
One Common Master-Data Mechanism
One Common Configuration Mechanism
One Common Identifier-Sequence Mechanism
One Common Geographic Reference Foundation
```

for the ERP.

---

# 66. Source Alignment

The project module architecture explicitly identifies Foundation as a
common layer used by almost every other module and lists Master Data,
Document Management, Authentication/RBAC, Notifications, and Audit/History
among the broader foundation capabilities.

The current PostgreSQL schema classification specifically assigns these
eight tables to the Foundation Module:

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

The project architecture also establishes the principles of configuration
over hardcoding and Master Data Driven design.

---

# 67. Status

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
