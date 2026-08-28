# NSS ERP — Reports & Analytics Table Design

**Document ID:** SOL-RPT-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Reports & Analytics
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the physical-data ownership boundary for the Reports &
Analytics Module.

The key principle is:

    Reports owns reporting metadata and configuration.

    Business modules own transactional data.

Reports shall query authoritative source data rather than duplicate it.

---

# 2. Core Design Principle

The Reports Module shall NOT create duplicate transactional tables for:

    Person
    Membership
    Attendance
    Family
    Governance
    Youth
    UPBS
    Organization

Those modules remain authoritative.

---

# 3. Proposed Reports-Owned Tables

The initial Reports-owned persistence model is intentionally small.

| # | Table | Purpose |
|---:|---|---|
| 1 | `report_category_master` | Report category catalogue |
| 2 | `report_definition` | Registered report definitions |
| 3 | `report_filter_definition` | Supported filters for reports |
| 4 | `dashboard` | Dashboard definitions |
| 5 | `dashboard_widget` | Dashboard widget definitions |

These are metadata/configuration entities.

They do not replace source business data.

---

# 4. Optional / Not Yet Frozen Tables

The following are deliberately NOT frozen:

    report_execution
    report_snapshot
    report_schedule
    report_export
    report_metric_definition
    reporting_fact_*
    reporting_dimension_*
    materialized reporting tables

These should only be introduced when an actual requirement justifies them.

---

# 5. `report_category_master`

## 5.1 Purpose

Defines the categories under which reports are organized.

Initial categories:

    MEMBERSHIP
    ATTENDANCE
    FAMILY
    GOVERNANCE
    YOUTH
    UPBS

---

## 5.2 Primary Key

```text
report_category_master_pk
```

UUID technical primary key.

---

## 5.3 Business Identity

```text
report_category_code
```

must be unique.

Example:

```text
MEMBERSHIP
ATTENDANCE
GOVERNANCE
```

---

## 5.4 Logical Columns

```text
report_category_master_pk
report_category_code
report_category_name
description
display_order
is_active

created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

The audit columns follow the project database standard.

---

# 6. `report_definition`

## 6.1 Purpose

Represents a registered report in the ERP.

Examples:

```text
MEMBER_COUNT
ATTENDANCE_SUMMARY
CURRENT_GOVERNANCE_BODY
FAMILY_SUMMARY
UPBS_REGISTRATION_SUMMARY
```

---

## 6.2 Primary Key

```text
report_definition_pk
```

UUID.

---

## 6.3 Foreign Key

```text
report_category_master_pk
```

references:

```text
report_category_master.report_category_master_pk
```

---

## 6.4 Logical Columns

```text
report_definition_pk

report_code
report_name
description

report_category_master_pk

source_module

visibility_level

is_active
display_order

created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

---

# 7. Report Code

`report_code` is the permanent business identifier of the report.

Example:

```text
RPT-MEM-001
RPT-ATT-001
RPT-GOV-001
```

It shall be unique.

---

# 8. Report Name

`report_name` is the human-readable name.

Example:

```text
Membership Summary
Attendance Summary
Current Governance
```

---

# 9. Source Module

`source_module` identifies the authoritative business module.

Initial values:

```text
MEMBERSHIP
ATTENDANCE
FAMILY
GOVERNANCE
YOUTH
UPBS
```

The source module is a logical reference.

It should not create unnecessary cross-module FK dependencies.

---

# 10. Report Visibility

A report may have an associated visibility level.

Possible logical values:

```text
MEMBER
SAKHA
ANCHALIKA
ZILLA
KENDRA
GOVERNANCE
ADMINISTRATION
```

The final authorization model remains centralized in Administration/RBAC.

---

# 11. Report Definition Lifecycle

A report definition may conceptually progress through:

```text
DRAFT
ACTIVE
RETIRED
```

Exact status values require final master-data approval.

---

# 12. Retired Reports

A retired report shall not normally be physically deleted if it has historical
usage or traceability implications.

Historical report definitions should remain identifiable.

---

# 13. `report_filter_definition`

## 13.1 Purpose

Defines which filters are available for a particular report.

Examples:

```text
Date Range
Year
Sakha
Zilla
Membership Type
Membership Status
Gender
Governance Body
```

---

## 13.2 Primary Key

```text
report_filter_definition_pk
```

UUID.

---

## 13.3 Foreign Key

```text
report_definition_pk
```

references:

```text
report_definition.report_definition_pk
```

---

## 13.4 Logical Columns

```text
report_filter_definition_pk

report_definition_pk

filter_code
filter_name
filter_type

is_required
display_order
is_active

created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

---

# 14. Filter Type

Possible logical filter types:

```text
TEXT
NUMBER
DATE
DATE_RANGE
BOOLEAN
SINGLE_SELECT
MULTI_SELECT
ORGANIZATION
MEMBERSHIP_TYPE
MEMBERSHIP_STATUS
```

This catalogue is not yet frozen.

---

# 15. Filter Source

A filter may obtain its selectable values from an authoritative source.

Example:

```text
Sakha Filter
    ↓
Organization Module
```

Reports must not duplicate Sakha master data.

---

# 16. Required Filter

A report may define a filter as:

```text
required
```

or:

```text
optional
```

Example:

```text
Attendance Report
    Date Range = Required
```

The exact required-filter matrix is report-specific.

---

# 17. Filter Validation

Filter values must be validated before report execution.

Invalid values shall not reach the reporting query.

---

# 18. `dashboard`

## 18.1 Purpose

Represents a configured analytical dashboard.

Examples:

```text
Kendra Dashboard
Membership Dashboard
Attendance Dashboard
Governance Dashboard
```

---

## 18.2 Primary Key

```text
dashboard_pk
```

UUID.

---

## 18.3 Logical Columns

```text
dashboard_pk

dashboard_code
dashboard_name
description

visibility_level

is_active
display_order

created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

---

# 19. Dashboard Code

`dashboard_code` shall be unique.

Example:

```text
DASH-KENDRA-001
DASH-MEM-001
DASH-ATT-001
```

---

# 20. Dashboard Visibility

Dashboard visibility shall follow centralized authorization.

A dashboard does not grant access to the underlying data by itself.

---

# 21. `dashboard_widget`

## 21.1 Purpose

Represents an individual visual/analytical component within a dashboard.

Examples:

```text
Total Members
Attendance %
Membership Growth
Active Sakhas
Vacancies
Upcoming UPBS
```

---

## 21.2 Primary Key

```text
dashboard_widget_pk
```

UUID.

---

## 21.3 Foreign Key

```text
dashboard_pk
```

references:

```text
dashboard.dashboard_pk
```

---

# 22. Logical Columns

```text
dashboard_widget_pk

dashboard_pk

widget_code
widget_title
widget_type

report_definition_pk

display_order

configuration_json

is_active

created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

---

# 23. Widget Type

Possible widget types:

```text
KPI
TABLE
BAR_CHART
LINE_CHART
PIE_CHART
AREA_CHART
SUMMARY
```

The exact supported catalogue is pending UI design.

---

# 24. Widget → Report Relationship

A widget may reference a report definition where appropriate.

Conceptually:

```text
dashboard
    ↓
dashboard_widget
    ↓
report_definition
    ↓
report query
```

---

# 25. Configuration JSON

`configuration_json` may contain presentation configuration such as:

```text
Chart Type
Display Settings
Column Selection
Ordering
Formatting
```

It must not be used to store authoritative transactional data.

---

# 26. Report Data Is Not Stored Here

The following must NOT be stored inside `configuration_json`:

```text
Member Records
Attendance Records
Family Records
Governance Assignments
UPBS Registrations
```

It is configuration only.

---

# 27. Source Transactional Tables

Reports directly depends logically on authoritative source tables.

Examples:

```text
Membership
    ↓
report_definition

Attendance
    ↓
report_definition

Governance
    ↓
report_definition
```

No duplicate reporting copy is required by this design.

---

# 28. Database Views

PostgreSQL views may be introduced where they simplify complex report
queries.

Examples:

```text
vw_membership_summary
vw_attendance_summary
vw_current_governance
```

These are implementation artifacts, not Reports business tables.

They shall only be created after the individual report/query requirement is
approved.

---

# 29. Materialized Views

Materialized views may be introduced for expensive analytical reports where
performance requires precomputed results.

Examples:

```text
membership_monthly_summary
attendance_monthly_summary
```

No materialized view is frozen by this document.

---

# 30. Reporting Tables

Dedicated derived reporting tables may be introduced only when:

```
Query performance requires them
Data snapshotting requires them
Reporting workload justifies them
```

They must remain explicitly derived from authoritative source data.

---

# 31. No Duplicate Fact Tables

Do not create tables such as:

```text
fact_membership
fact_attendance
fact_family
fact_governance
```

at this stage.

A data-warehouse/star-schema architecture has not been approved.

---

# 32. No Duplicate Dimension Tables

Do not create reporting copies such as:

```text
dim_person
dim_sakha
dim_membership
dim_governance
```

unless a future analytics architecture explicitly approves them.

---

# 33. Organization Reference

Reports shall use the authoritative Organization data.

Do not create:

```text
report_sakha
report_zilla
report_anchalika
```

tables.

---

# 34. Person Reference

Reports shall use authoritative Person identity.

Do not create:

```text
report_person
```

as a duplicate identity table.

---

# 35. Membership Reference

Reports shall use authoritative Membership identity.

Do not create:

```text
report_membership
```

as a duplicate membership table.

---

# 36. Attendance Reference

Reports shall use authoritative Attendance records.

Do not create:

```text
report_attendance
```

as a second attendance system of record.

---

# 37. Family Reference

Reports shall use authoritative Family records.

Do not create:

```text
report_family
```

as a second family system of record.

---

# 38. Governance Reference

Reports shall use authoritative Governance records.

Do not create:

```text
report_governance
```

as a second governance system of record.

---

# 39. UPBS Reference

Reports shall use authoritative UPBS records.

Do not create:

```text
report_upbs
```

as a second UPBS system of record.

---

# 40. Youth Reference

Reports shall use authoritative Youth module records.

Do not create duplicate Youth transaction tables in Reports.

---

# 41. Report Execution

A `report_execution` table is NOT currently frozen.

For the first implementation, execution may remain an application/service
operation without persistence.

---

# 42. Execution History

Future requirements may justify:

```text
report_execution
```

for:

```
Execution Audit
Performance Monitoring
Download History
Snapshot Reproduction
```

This is pending.

---

# 43. Report Snapshot

A snapshot table is NOT currently frozen.

If a report must reproduce a historical published result exactly, a future
snapshot mechanism may be introduced.

---

# 44. Report Scheduling

A `report_schedule` table is NOT currently frozen.

Scheduled reporting is a future capability.

---

# 45. Report Export

A dedicated `report_export` table is NOT currently frozen.

PDF/Excel/CSV generation may initially be stateless.

---

# 46. Report Metrics

A separate `report_metric_definition` table is NOT currently frozen.

If KPI definitions become sufficiently complex, a dedicated metric model
may be introduced later.

---

# 47. Audit Columns

Reports-owned persistent tables shall follow the project audit convention:

```text
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk

is_active
```

This follows the project-wide database standard.

---

# 48. Primary Key Convention

Technical primary keys shall follow:

```text
<table_name>_pk
```

Examples:

```text
report_definition_pk
dashboard_pk
dashboard_widget_pk
```

This follows the established project database convention.

---

# 49. Foreign Key Convention

Foreign keys shall reference the technical PK:

```text
report_definition_pk
dashboard_pk
report_category_master_pk
```

rather than using business identifiers as FK columns.

---

# 50. Business Identifier Convention

Where a persistent Reports entity requires a business identifier:

```text
report_code
dashboard_code
widget_code
report_category_code
```

shall be used separately from the technical UUID PK.

---

# 51. Soft Delete

Reports metadata should follow the project-wide soft-delete principle.

Historical report definitions should not be physically deleted where doing
so would break traceability.

---

# 52. Referential Integrity

The database shall enforce valid relationships between:

```text
report_category_master
        ↓
report_definition
        ↓
report_filter_definition
```

and:

```text
dashboard
        ↓
dashboard_widget
        ↓
report_definition
```

---

# 53. Delete Behaviour

Deleting a report category shall not silently delete historical report
definitions.

Deleting a dashboard shall not silently remove unrelated report definitions.

The final PostgreSQL `ON DELETE` rules belong to DDL.

---

# 54. Uniqueness

The following should be unique:

```text
report_category_code
report_code
dashboard_code
widget_code
```

Composite uniqueness may be required for:

```text
dashboard_pk + widget_code
```

if widget codes are only unique within a dashboard.

---

# 55. Report Filter Uniqueness

A report should not contain duplicate filter definitions for the same
logical filter.

Potential uniqueness:

```text
report_definition_pk
filter_code
```

---

# 56. Dashboard Widget Ordering

Each dashboard widget should have an explicit display order.

This permits deterministic dashboard rendering.

---

# 57. Dashboard Widget Configuration

Configuration should be validated according to widget type.

Example:

```text
LINE_CHART
    → X-axis
    → Y-axis
    → metric

KPI
    → metric
```

Exact UI configuration belongs to later functional design.

---

# 58. Source Module Validation

`source_module` should be restricted to approved reporting source modules.

Initial values:

```text
MEMBERSHIP
ATTENDANCE
FAMILY
GOVERNANCE
YOUTH
UPBS
```

---

# 59. Report Category Validation

Report category should reference:

```text
report_category_master
```

rather than arbitrary free text.

---

# 60. Dashboard Report Dependency

If a dashboard widget references a report, the report definition must remain
available while the dashboard remains active.

Retirement rules must preserve historical traceability.

---

# 61. Reporting Metadata vs Business Data

The separation is:

```text
Reports Module
────────────────────────────
Metadata
Configuration
Definitions
Dashboards
Widgets

Business Modules
────────────────────────────
Transactional Data
Master Data
Business History
Business Rules
```

---

# 62. Logical ERD

```text
┌──────────────────────────────┐
│ report_category_master       │
│                              │
│ report_category_master_pk    │
│ report_category_code         │
│ report_category_name         │
└───────────────┬──────────────┘
                │ 1:N
                ▼
┌──────────────────────────────┐
│ report_definition            │
│                              │
│ report_definition_pk         │
│ report_code                  │
│ report_category_master_pk    │
│ source_module                │
│ visibility_level             │
└───────────────┬──────────────┘
                │ 1:N
                ▼
┌──────────────────────────────┐
│ report_filter_definition     │
│                              │
│ report_filter_definition_pk  │
│ report_definition_pk         │
│ filter_code                  │
│ filter_type                  │
└──────────────────────────────┘


┌──────────────────────────────┐
│ dashboard                    │
│                              │
│ dashboard_pk                 │
│ dashboard_code               │
│ dashboard_name               │
│ visibility_level             │
└───────────────┬──────────────┘
                │ 1:N
                ▼
┌──────────────────────────────┐
│ dashboard_widget             │
│                              │
│ dashboard_widget_pk          │
│ dashboard_pk                 │
│ report_definition_pk         │
│ widget_type                  │
│ configuration_json           │
└───────────────┬──────────────┘
                │
                ▼
        Report / Metric Query
                │
                ▼
     ┌──────────┼───────────┐
     ▼          ▼           ▼
 Membership Attendance  Governance
     │          │           │
     └──────────┼───────────┘
                ▼
         Other Source Modules
```

---

# 63. Source Module Boundary

The physical source tables remain in:

```text
Membership
Attendance
Family
Governance
Kumari
Kishor
UPBS
Organization
Person
```

Reports references them through queries/services/views.

---

# 64. Reporting Architecture

The final logical data path is:

```text
Authoritative Source
        ↓
Query / View / Service
        ↓
Report Definition
        ↓
Report Result
        ↓
Dashboard / Export
```

---

# 65. Tables Owned by Reports

The currently approved Reports-owned persistence boundary is:

```text
report_category_master
report_definition
report_filter_definition
dashboard
dashboard_widget
```

---

# 66. Tables Not Owned by Reports

Reports does not own:

```text
person
sangha_sevi
attendance
family
governance bodies
governance assignments
kumari records
kishor records
UPBS transactions
organization
```

---

# 67. Physical Query Objects

Potential future PostgreSQL objects:

```text
VIEW
MATERIALIZED VIEW
FUNCTION
INDEX
```

must be created based on actual report requirements.

They are not automatically part of the Reports schema.

---

# 68. Performance Rule

A report should initially use the simplest reliable query architecture.

Optimization should be introduced when actual workload demonstrates a need.

Possible progression:

```text
Direct Query
    ↓
Optimized Query
    ↓
View
    ↓
Materialized View
    ↓
Derived Reporting Table
```

No unnecessary layer should be introduced prematurely.

---

# 69. Historical Reporting

Historical reports must use historical data from the source module.

Reports must not reconstruct history from current-state fields if the source
module already provides authoritative historical records.

---

# 70. Report Metadata History

Where a report definition changes materially, project traceability must allow
the change to be identified.

The exact versioning mechanism remains pending.

---

# 71. API Boundary

This table design does not define API endpoints.

API design follows after the reporting data model is approved.

---

# 72. UI Boundary

This table design does not define functional dashboard/report screens.

Functional UI design follows API design.

---

# 73. SQL Boundary

This document defines the logical physical data model but does not provide
PostgreSQL DDL.

DDL will be generated only after:

```
Table Design Review
Naming Review
Constraint Review
Cross-Module FK Review
```

---

# 74. Current Table Count

Reports-owned metadata tables:

```
5
```

```text
1. report_category_master
2. report_definition
3. report_filter_definition
4. dashboard
5. dashboard_widget
```

No additional reporting transaction tables are currently frozen.

---

# 75. Future Expansion

Future tables may be added for:

```text
report_execution
report_snapshot
report_schedule
report_metric_definition
```

only when approved requirements justify them.

---

# 76. Source Alignment

The project architecture establishes:

```text
Person ≠ Member
Family First
Membership ID = Sangha Sevi ID
Unified Body Governance Model
History Never Deleted
Master Data Driven
By-Law Supremacy
Documentation First
Configuration Over Hardcoding
Auditability
```

These principles apply to Reports as well.

The project database standard establishes:

```text
<table_name>_pk
```

for technical primary keys, PK-based foreign keys, and the standard audit
columns:

```text
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
deleted_at
deleted_by_sangha_sevi_pk
```

---

# 77. Status

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
