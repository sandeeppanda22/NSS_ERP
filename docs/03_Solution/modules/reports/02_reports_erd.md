# NSS ERP — Reports & Analytics Reporting Architecture

**Document ID:** SOL-RPT-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Reports & Analytics
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical data architecture of the Reports &
Analytics Module.

Reports is a cross-module read/analytics capability.

It consumes authoritative data from business modules and produces:

    Reports
    Dashboards
    Analytics
    Aggregations
    Exports

It does not become the system of record for those business domains.

---

# 2. Core Architecture

The logical reporting architecture is:

    Authoritative Modules
            ↓
    Reporting Query / Analytics Layer
            ↓
    Report Definitions
            ↓
    Report Output
            ↓
    Dashboard / Export / Analytics

---

# 3. Source Modules

Initial reporting sources are:

    Membership
    Attendance
    Family
    Governance
    Youth
    UPBS

These are the initial frozen report families identified for Reports &
Analytics.

---

# 4. High-Level Architecture

```text
┌───────────────────────────────────────────────────────────────┐
│                  AUTHORITATIVE BUSINESS MODULES               │
├──────────────┬────────────┬──────────┬──────────┬───────┬─────┤
│ Membership   │ Attendance │ Family   │Governance │ Youth │ UPBS│
└──────┬───────┴──────┬─────┴─────┬────┴─────┬────┴───┬───┴──┬──┘
       │              │            │          │        │      │
       └──────────────┴────────────┴──────────┴────────┴──────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Reporting Layer  │
                    └────────┬─────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
          Report Query   Aggregation    Analytics
               │             │             │
               └─────────────┼─────────────┘
                             ▼
                    ┌──────────────────┐
                    │ Report Definition│
                    └────────┬─────────┘
                             │
                 ┌───────────┼────────────┐
                 ▼           ▼            ▼
              Report     Dashboard     Export
```

---

# 5. Reporting Is Not a Transactional Domain

Reports does not own:

```
Person
Membership
Attendance
Family
Governance
Youth
UPBS
```

records.

Those records remain owned by their respective modules.

---

# 6. Authoritative Source Principle

Every reporting dataset must have an identifiable authoritative source.

Example:

```text
Membership Report
       ↓
Membership Data

Attendance Report
       ↓
Attendance Data

Governance Report
       ↓
Governance Data
```

---

# 7. Report Definition

A report definition represents the logical definition of a supported report.

Conceptually:

```text
report_definition
```

contains/report-identifies:

```
Report Code
Report Name
Category
Source Module
Description
Visibility
Supported Filters
Output Options
```

The physical table is not yet frozen.

---

# 8. Report Category

A report belongs to a reporting category.

Initial categories:

```
MEMBERSHIP
ATTENDANCE
FAMILY
GOVERNANCE
YOUTH
UPBS
```

---

# 9. Report Definition Relationship

Conceptually:

```text
report_category
       │
       │ 1:N
       ▼
report_definition
```

The exact physical representation of `report_category` is not yet frozen.

It may ultimately be:

```
Master Data
Enumeration
Dedicated Table
```

The final choice belongs to Table Design.

---

# 10. Report Data Source

A report definition identifies its source module.

Conceptually:

```text
report_definition
       │
       ▼
source_module
```

Possible values:

```
MEMBERSHIP
ATTENDANCE
FAMILY
GOVERNANCE
YOUTH
UPBS
```

---

# 11. Report Query

A report definition maps to the query/analytics logic required to produce
the report.

Conceptually:

```text
report_definition
       │
       ▼
report_query
       │
       ▼
authoritative source data
```

The exact implementation may be:

```
Django QuerySet
SQL View
PostgreSQL View
Materialized View
Reporting Service
Aggregation Service
```

No one implementation is frozen yet.

---

# 12. Report Output

The logical report output is generated from the reporting query.

```text
report_definition
       │
       ▼
report execution
       │
       ▼
report result
```

A report result may be rendered as:

```
Screen
Dashboard
PDF
Excel
CSV
```

---

# 13. Report Execution

A report execution is a logical operation:

```text
User
  ↓
Authorization
  ↓
Report Definition
  ↓
Filters
  ↓
Source Query
  ↓
Result
```

The exact persistence of report executions is not frozen.

---

# 14. Report Filters

Reports may support reusable filters.

Conceptually:

```text
report_definition
       │
       ▼
report_filter_definition
```

Examples:

```
Date Range
Year
Organization
Kendra
Anchalika
Zilla
Sakha
Membership Type
Membership Status
Gender
Age Group
Event
Governance Body
```

Not every filter applies to every report.

---

# 15. Filter Values

Filter values should reference authoritative source entities where
appropriate.

Example:

```text
Sakha Filter
    ↓
Organization Module
```

rather than maintaining a second Sakha master inside Reports.

---

# 16. Organization Relationship

Reporting uses the authoritative Organization hierarchy.

Conceptually:

```text
Organization
     │
     ├── Kendra
     ├── Anchalika
     ├── Zilla
     └── Sakha
              │
              ▼
       Report Filtering
```

Reports does not create an independent organization hierarchy.

---

# 17. Person Relationship

Reports uses the authoritative Person identity.

```text
Person
   │
   ▼
Reporting Queries
```

No duplicate Person table is created for reporting.

---

# 18. Membership Relationship

Reports consumes Membership data.

```text
Membership
    │
    ▼
Membership Reports
```

Examples:

```
Active Members
Renewal
Membership Type
Membership Status
Membership Growth
```

---

# 19. Attendance Relationship

Reports consumes Attendance data.

```text
Attendance
    │
    ▼
Attendance Reports
```

Examples:

```
Attendance Percentage
Attendance Trend
Member Attendance
Sangha Attendance
```

The Attendance Module remains authoritative for attendance calculations.

---

# 20. Family Relationship

Reports consumes Family data.

```text
Family
   │
   ▼
Family Reports
```

Examples:

```
Family Count
Family Size
Family Composition
Family Participation
```

---

# 21. Governance Relationship

Reports consumes Governance data.

```text
Governance
    │
    ▼
Governance Reports
```

Examples:

```
Current Office Holders
Historical Office Holders
Body Composition
Vacancies
Acting Positions
Election Results
```

---

# 22. Youth Relationship

Reports consumes Youth-module data.

Conceptually:

```text
Kumari
   │
Kishor
   │
   ▼
Youth Reporting
```

The exact source modules are authoritative for their own business rules.

---

# 23. UPBS Relationship

Reports consumes UPBS data.

```text
UPBS
  │
  ▼
UPBS Reports
```

Examples:

```
Registration
Delegate
Accommodation
Participation
Committee
Event
```

---

# 24. Cross-Module Reporting

Reports may combine multiple authoritative sources.

Example:

```text
Person
  │
  ├── Membership
  │
  ├── Family
  │
  └── Attendance
          │
          ▼
     Cross-Module Report
```

---

# 25. Cross-Module Identity

Cross-module reporting must use stable identifiers.

Conceptually:

```text
Person
   │
   ├── Membership
   ├── Family
   ├── Attendance
   └── Governance
```

Display names must not be treated as primary identity keys.

---

# 26. Reporting Data Flow

```text
Membership ─────┐
Attendance ─────┤
Family ─────────┤
Governance ─────┤
Youth ──────────┤
UPBS ───────────┤
                ▼
        Reporting Query Layer
                │
                ▼
        Report Definition
                │
                ▼
        Report Result
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
     Screen  Dashboard  Export
```

---

# 27. Dashboard Architecture

A dashboard is a presentation layer over reporting/analytics data.

Conceptually:

```text
dashboard
    │
    ├── KPI
    ├── Chart
    ├── Table
    └── Trend
```

The physical persistence of dashboards is not currently frozen.

---

# 28. Dashboard Widget

A dashboard may contain multiple analytical widgets.

Conceptually:

```text
dashboard
    │
    └──< dashboard_widget
```

A widget may reference:

```
Report
Metric
Query
Chart configuration
```

The physical schema is pending.

---

# 29. KPI Architecture

A KPI represents a calculated business metric.

Conceptually:

```text
KPI Definition
      │
      ▼
Source Data
      │
      ▼
Calculation
      │
      ▼
KPI Value
```

The metric definition must follow the source module's business rules.

---

# 30. Calculated Metrics

Calculated metrics must not contradict source-module rules.

Example:

```text
Attendance %
    =
Attended Eligible Sessions
/
Applicable Sessions
```

The exact formula is owned by Attendance.

Reports consumes that definition.

---

# 31. Historical Reporting

Reports must support historical queries where the source modules preserve
historical data.

Example:

```text
Governance
    ↓
Historical Assignments
    ↓
Historical Governance Report
```

---

# 32. Current-State Reporting

Reports may provide current-state views.

Example:

```text
Current President
Current Membership
Current Sakha Strength
```

Current-state reports must not accidentally include historical records.

---

# 33. Temporal Reporting

Reports may operate across:

```
Date
Month
Quarter
Year
Membership Year
Financial Year
Governance Term
```

The authoritative module defines the meaning of each period.

---

# 34. Reporting Period

A reporting period is a filter/concept, not necessarily a physical table.

The final implementation shall determine whether reusable reporting periods
need persistence.

---

# 35. Reporting Scope

Every report execution must operate within the user's authorized
organizational scope.

```text
User
  ↓
Authorized Scope
  ↓
Report
  ↓
Filtered Data
```

---

# 36. Scope Enforcement

Changing a report filter must never allow a user to bypass organizational
authorization.

Example:

```text
Sakha User
    ✕
Kendra Confidential Report
```

unless explicitly authorized.

---

# 37. RBAC Relationship

Reports use centralized RBAC.

Conceptually:

```text
User
  ↓
Role
  ↓
Permission
  ↓
Report Access
```

No separate reporting permission system is required.

---

# 38. Report Visibility

Report visibility may be:

```
Member
Sakha
Anchalika
Zilla
Kendra
Governance
Administration
```

The exact permission matrix belongs to Administration/RBAC.

---

# 39. Export Architecture

A report result may be passed to an export renderer:

```text
Report Result
     │
     ├── PDF
     ├── Excel
     └── CSV
```

The export layer must preserve report authorization.

---

# 40. Export Does Not Create New Data Authority

Exported files are representations of report results.

They do not become authoritative records.

---

# 41. Report Snapshot

Some reports may require reproducibility.

Conceptually:

```text
Report Execution
       │
       ▼
Snapshot
```

Snapshot persistence is not currently frozen.

---

# 42. Real-Time vs Derived Reporting

Two logical reporting modes are possible:

```text
Live Query
    ↓
Current Source Data
```

or:

```text
Source Data
    ↓
Derived Reporting Structure
    ↓
Report
```

The project has not frozen the choice globally.

---

# 43. PostgreSQL Views

Database views may be used where they provide a clean reporting abstraction.

Example:

```text
vw_membership_summary
vw_attendance_summary
vw_governance_current_positions
```

These are implementation candidates, not frozen tables.

---

# 44. Materialized Views

Materialized views may be used for expensive analytical queries where
performance requires precomputed results.

Example:

```text
membership_monthly_summary
attendance_monthly_summary
```

Again, these are implementation candidates, not frozen schema entities.

---

# 45. Reporting Tables

Dedicated derived reporting tables may be introduced only when justified by
performance or historical snapshot requirements.

They shall remain derived from authoritative modules.

---

# 46. No Premature Star Schema

A warehouse-style star schema is not currently frozen.

Do not introduce:

```
fact_membership
fact_attendance
fact_governance
```

merely because the system contains analytics.

Such a design requires separate approval and workload analysis.

---

# 47. No Duplicate Transaction Tables

The reporting architecture shall not duplicate:

```
Membership Transactions
Attendance Transactions
Governance Assignments
Family Transactions
UPBS Transactions
```

as independent systems of record.

---

# 48. Reporting Query Layer

The reporting query layer is the logical abstraction between source modules
and report outputs.

Conceptually:

```text
Source Modules
      │
      ▼
Reporting Query Layer
      │
      ▼
Report Definition
```

The physical implementation may reside in:

```
Django
PostgreSQL
FastAPI/reporting service
```

according to the final API architecture.

---

# 49. Report Definition Relationship

Logical relationship:

```text
report_definition
      │
      ├── source module
      ├── filters
      ├── query/metric
      └── output options
```

---

# 50. Dashboard Relationship

Logical relationship:

```text
dashboard
    │
    └──< dashboard_widget
                │
                ▼
          Report / Metric
```

---

# 51. Report Execution Relationship

Logical model:

```text
User
  │
  ▼
Report Definition
  │
  ▼
Report Parameters
  │
  ▼
Report Execution
  │
  ▼
Result
```

---

# 52. Report Execution Persistence

Persistence of report executions is not currently frozen.

Possible implementation:

```
No persistence
Audit-only
Execution history
Snapshot
```

Final choice belongs to later design.

---

# 53. Report Scheduling

Future scheduled reporting may use:

```text
report_definition
      │
      ▼
report_schedule
      │
      ▼
report_execution
```

Scheduling is not part of the current frozen table set.

---

# 54. Notification Relationship

Scheduled or triggered reports may use the common Notification capability.

```text
Report
  │
  ▼
Notification
```

Reports does not own Notification infrastructure.

---

# 55. Audit Relationship

Sensitive reporting operations may use the common Audit framework.

```text
Report Access / Export
        │
        ▼
      Audit
```

Reports does not create a separate audit system.

---

# 56. Error Boundary

A reporting failure must not corrupt source-module data.

```text
Report Failure
     ✕
Source Transaction
```

---

# 57. Read-Only Principle

Ordinary report execution is read-oriented.

```text
Report
  ↓
READ
```

It must not mutate transactional records.

---

# 58. Report-to-Source Traceability

Every production report should be traceable to its source.

Example:

```text
RPT-MEM-001
    ↓
Membership
    ↓
Membership Business Rule
    ↓
Report Query
```

---

# 59. Report Data Ownership

```text
┌──────────────────────┬────────────────────────┐
│ Data                 │ Owner                  │
├──────────────────────┼────────────────────────┤
│ Person               │ Person                 │
│ Membership           │ Membership             │
│ Attendance           │ Attendance             │
│ Family               │ Family                 │
│ Governance           │ Governance             │
│ Youth                │ Youth Modules          │
│ UPBS                 │ UPBS                   │
│ Report Definition    │ Reports                │
│ Dashboard Definition │ Reports                │
│ Export               │ Reports                │
└──────────────────────┴────────────────────────┘
```

---

# 60. Logical ERD

```text
                         ┌─────────────────────┐
                         │ report_definition   │
                         └──────────┬──────────┘
                                    │
                         ┌──────────┼───────────┐
                         │          │           │
                         ▼          ▼           ▼
                  report_filters  report_query  output_options
                                      │
                                      ▼
                             Authoritative Sources
                                      │
                ┌─────────────────────┼──────────────────────┐
                │          │          │          │            │
                ▼          ▼          ▼          ▼            ▼
           Membership  Attendance   Family   Governance    Youth
                                                              │
                                                              ▼
                                                             UPBS


                     ┌─────────────────────┐
                     │      dashboard      │
                     └──────────┬──────────┘
                                │
                                │ 1:N
                                ▼
                     ┌─────────────────────┐
                     │  dashboard_widget   │
                     └──────────┬──────────┘
                                │
                                ▼
                       Report / Metric
```

---

# 61. Logical Relationship Matrix

| Source            | Target            | Relationship  |
| ----------------- | ----------------- | ------------- |
| Report Category   | Report Definition | 1:N           |
| Report Definition | Report Filters    | 1:N           |
| Report Definition | Report Query      | 1:1 / logical |
| Dashboard         | Dashboard Widget  | 1:N           |
| Dashboard Widget  | Report/Metric     | N:1 / logical |
| Report Definition | Source Module     | N:1 / logical |
| Report Execution  | Report Definition | N:1 / logical |
| Report Execution  | User              | N:1 / logical |
| Report Execution  | Export            | 1:N / logical |

These are logical relationships only until the physical table design is
approved.

---

# 62. No Physical Source FK Assumption

A report definition should identify its source module logically.

It does not necessarily require a database FK to every source module.

For example:

```text
report_definition.source_module
```

may identify:

```
MEMBERSHIP
ATTENDANCE
GOVERNANCE
```

without introducing cross-module database coupling.

---

# 63. Cross-Module Database Boundary

The reporting architecture should avoid unnecessary physical coupling
between every business module and Reports.

Business modules remain independently responsible for their data integrity.

---

# 64. Data Consistency

Reports must use committed/valid source data.

If a report spans multiple modules, the implementation must consider
consistent read behaviour.

The exact transaction/isolation strategy is an implementation decision.

---

# 65. Performance Architecture

Reporting queries must not unnecessarily degrade operational transactions.

Where required, the implementation may use:

```
Indexes
Views
Materialized Views
Aggregations
Caching
Read Replicas
```

These are implementation options.

---

# 66. Reporting Cache

A cache may be introduced for frequently requested analytical data.

Cache invalidation and freshness rules must be defined before production
use.

---

# 67. Report Security Boundary

The security flow is:

```text
Authentication
      ↓
RBAC
      ↓
Organizational Scope
      ↓
Report Authorization
      ↓
Report Query
```

The reporting query must not execute before authorization is established.

---

# 68. Sensitive Reporting

Reports containing restricted data require appropriate authorization.

Examples may include:

```
Governance-sensitive information
Personal information
Attendance details
Administrative data
Financial/UPBS information
```

---

# 69. Member-Facing Reporting

Member-facing reports must be restricted to:

```
Own Information
Authorized Family Information
Approved Public/Member Reports
```

The exact visibility matrix is not frozen here.

---

# 70. Historical Governance Reporting

Governance reports should derive historical office-holder information from
the Governance assignment history.

Reports shall not maintain a second office-holder history.

---

# 71. Historical Attendance Reporting

Attendance reports shall derive attendance history from Attendance.

Reports shall not create an alternative attendance history.

---

# 72. Membership Trend Reporting

Membership growth analytics should derive from Membership history and
business rules.

The report layer should not independently infer membership lifecycle.

---

# 73. Family Analytics

Family analytics should derive from Family relationships.

Reports must respect Family visibility rules.

---

# 74. Youth Analytics

Youth reports must respect the applicable Kumari/Kishor privacy and
visibility rules.

---

# 75. UPBS Analytics

UPBS reports must respect UPBS authorization and organizational scope.

---

# 76. Report Catalogue Expansion

Adding a new report should normally require:

```
New Report Definition
Query/Metric Definition
Authorization
Test
Documentation
```

It should not require creating a new transactional domain.

---

# 77. Report Categories Expansion

New report categories may be added later.

Examples:

```
Sevak
Publications
Heritage
Administration
```

This should not require redesign of the reporting architecture.

---

# 78. Future Reporting Architecture

The logical architecture intentionally allows evolution:

```text
Phase 1
Live Queries
    ↓
Reports

Phase 2
Views / Optimized Queries
    ↓
Reports

Phase 3
Materialized / Derived Analytics
    ↓
Reports

Future
Dedicated Analytics / Warehouse
    ↓
Advanced Analytics
```

No later phase is automatically implied by this document.

---

# 79. API Boundary

The reporting architecture will eventually expose reporting functionality
through the project's API layer.

This document does not define endpoint contracts.

---

# 80. UI Boundary

The reporting architecture will eventually feed:

```
Report Pages
Dashboards
Charts
Tables
Export Controls
```

Functional UI is not defined here.

---

# 81. Table Design Boundary

The following remain intentionally unresolved:

```
Physical report_definition table
Report category storage
Filter-definition storage
Dashboard persistence
Dashboard widget persistence
Report execution persistence
Materialized views
Reporting tables
Snapshot tables
Scheduling tables
```

These belong to REPORTS-04 and later implementation decisions.

---

# 82. Current Frozen Logical Model

The current logical model is:

```text
Authoritative Business Modules
             │
             ▼
       Reporting Layer
             │
       ┌─────┴─────┐
       ▼           ▼
Report Definitions Dashboards
       │           │
       └─────┬─────┘
             ▼
        Report Output
             │
       ┌─────┼──────┐
       ▼     ▼      ▼
     Screen PDF   Excel/CSV
```

---

# 83. Source Alignment

The project source establishes Reports as a dedicated solution module and
places it alongside the other ERP modules rather than embedding reporting
inside Membership, Attendance, Governance or Administration.

The project UI/navigation source also identifies Reports as a primary ERP
navigation module alongside Membership, Family, Governance, Attendance,
Mahila Sangha, Kumari Sangha, Kishor Puja, Founder & Heritage, UPBS and
Administration.

The reporting architecture therefore preserves the project-wide modular
boundary: **business modules remain authoritative; Reports consumes them.**

---

# 84. Status

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
