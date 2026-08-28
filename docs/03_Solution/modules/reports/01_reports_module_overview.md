# NSS ERP — Reports & Analytics Module Overview

**Document ID:** SOL-RPT-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Reports & Analytics
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Reports & Analytics Module provides centralized reporting, analytical
views, dashboards, summaries and export capabilities across NSS ERP.

The module shall consume authoritative data from the respective business
modules.

It shall not become the owner of the underlying transactional data.

---

# 2. Core Principle

The Reports Module follows:

    Report Data
         ↓
    Authoritative Business Module
         ↓
    Report / Analytics View

Reports should derive information from the source-of-truth module.

---

# 3. Initial Frozen Scope

The project module division identifies the initial Reports & Analytics
scope as:

    Membership Reports
    Attendance Reports
    Family Reports
    Governance Reports
    Youth Reports
    UPBS Reports

---

# 4. Module Position

Reports is a cross-module capability.

Conceptually:

```text
Membership ────────┐
Attendance ────────┤
Family ────────────┤
Governance ────────┤
Youth ─────────────┤
UPBS ──────────────┤
                   ▼
          Reports & Analytics
                   │
          ┌────────┴────────┐
          ▼                 ▼
       Reports          Analytics
```

---

# 5. Ownership Principle

The Reports Module owns:

```
Report Definitions
Report Execution
Report Presentation
Report Filters
Report Exports
Analytical Aggregation
```

It does NOT own:

```
Membership
Attendance
Family
Governance
Youth
UPBS
```

transactional records.

---

# 6. Source-of-Truth Principle

Every report must identify its source module.

Examples:

```text
Membership Report
    → Membership

Attendance Report
    → Attendance

Family Report
    → Family

Governance Report
    → Governance

Youth Report
    → Kumari / Kishor / relevant Youth source

UPBS Report
    → UPBS
```

---

# 7. No Transaction Duplication

The Reports Module shall not maintain a second copy of transactional records
merely for reporting.

For example, Reports shall not create another:

```
sangha_sevi
```

or:

```
attendance
```

table as a replacement for the authoritative source.

---

# 8. Membership Reports

Initial Membership reporting may include:

```
Total Members
Active Members
Membership by Type
Membership by Status
Membership by Organization
Membership by Gender
Membership by Age Group
Membership by Year
Renewal Statistics
Transfer Statistics
Membership Growth
```

Exact report catalogue remains subject to detailed reporting requirements.

---

# 9. Attendance Reports

Initial Attendance reporting may include:

```
Attendance Summary
Attendance by Sangha
Attendance by Member
Attendance by Period
Attendance Percentage
Excused Absence Summary
Attendance Alerts
Attendance Trends
```

Attendance remains owned by the Attendance Module.

Reports only consume attendance data.

---

# 10. Family Reports

Initial Family reporting may include:

```
Family Count
Family Size
Family Composition
Family Relationship Summary
Family by Organization
Youth Visibility
Family Transition Statistics
```

Family data remains owned by the Family Module.

---

# 11. Governance Reports

Initial Governance reporting may include:

```
Current Office Holders
Historical Office Holders
Governance Body Composition
Position Assignments
Acting Positions
Vacancies
Election Results
Governance History
```

Governance remains the authoritative source.

---

# 12. Youth Reports

Youth reporting may cover:

```
Kumari Sangha
Kishor Puja
Youth Participation
Youth Activities
Youth Membership Transitions
Year-wise Participation
```

The Reports Module shall not redefine the underlying Youth business rules.

---

# 13. UPBS Reports

Initial UPBS reporting may include:

```
Registration Summary
Delegate Summary
Accommodation Summary
Committee Summary
Event Participation
Prasad Patra Summary
Financial/Collection Summary where authorized
UPBS Operational Statistics
```

UPBS remains the source-of-truth module.

---

# 14. Cross-Module Reports

The Reports Module may combine information from multiple authoritative
modules.

Examples:

```text
Member + Family + Attendance

Member + Membership + Governance

Family + Youth

Membership + UPBS

Organization + Membership + Attendance
```

Cross-module reporting must preserve the ownership boundaries of the source
modules.

---

# 15. Organizational Scope

Reports must respect the user's authorized organizational scope.

Possible scopes include:

```
Sakha
Anchalika
Zilla
Kendra
```

A user must not receive report data outside their authorized scope unless
explicitly permitted by the central authorization framework.

---

# 16. RBAC

Reports shall use the centralized ERP RBAC system.

The Reports Module shall not create a separate permission architecture.

---

# 17. Report Visibility

Different reports may have different visibility requirements.

Examples:

```
Member-facing
Sakha-level
Anchalika-level
Zilla-level
Kendra-level
Administrative
Governance-only
```

The exact visibility matrix will be finalized through the common
Administration/RBAC standards.

---

# 18. Member-Facing Reports

Where approved, members may receive limited reports relevant to themselves
or their authorized information.

Examples:

```
Personal Attendance
Membership Information
Personal Participation History
```

Member-facing reporting shall not expose restricted information.

---

# 19. Administrative Reports

Authorized administrators may access broader operational reports according
to organizational scope and RBAC.

---

# 20. Governance Reports

Governance-sensitive reports shall be restricted according to the applicable
governance authorization rules.

---

# 21. Report Filters

Reports should support appropriate filters such as:

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

# 22. Time-Based Reporting

Reports should support:

```
Daily
Weekly
Monthly
Quarterly
Annual
Financial/Administrative Year
Membership Year
```

The applicable period definition must come from the authoritative business
module rather than being independently invented by Reports.

---

# 23. Historical Reporting

Reports shall preserve the ability to report historical states.

Examples:

```
Members in a previous year
Office holders during a previous term
Attendance during a previous period
Historical membership status
Historical organization assignment
```

Historical reporting must use preserved source data.

---

# 24. Current vs Historical State

Reports should clearly distinguish:

```
Current State
```

from:

```
Historical State
```

Example:

```
Current President
Historical President
```

must not be treated as the same report concept.

---

# 25. Report Accuracy

Reports must derive from authoritative source data.

A report must not silently apply business rules that contradict the source
module.

---

# 26. Report Definition

A report should have a defined:

```
Report Code
Report Name
Description
Source Module
Required Permissions
Supported Filters
Output Format
```

The physical report-definition model will be finalized in Table Design.

---

# 27. Report Catalogue

The Reports Module should maintain a controlled catalogue of supported
reports.

A report should have a stable business identity.

---

# 28. Report Versioning

When a report's business definition changes materially, the change must be
traceable.

Historical report definitions should not make previous published reports
uninterpretable.

---

# 29. Export

Reports should support approved export formats such as:

```
PDF
Excel
CSV
```

The exact export availability depends on the individual report.

---

# 30. Export Security

Exports must respect the same authorization and organizational-scope rules
as on-screen reports.

A user must not gain additional access simply by exporting a report.

---

# 31. Export Audit

Sensitive report exports should be auditable where required by the common
Audit/Security standards.

---

# 32. Dashboards

Reports & Analytics may provide dashboards containing:

```
KPI Cards
Charts
Tables
Trends
Comparative Statistics
```

Dashboards shall derive data from authoritative source modules.

---

# 33. Dashboard vs Report

A dashboard is an analytical presentation.

A report is a defined information output.

They may use the same underlying reporting/query layer.

---

# 34. Analytics

Analytics may include:

```
Trends
Growth
Distribution
Comparisons
Ratios
Percentages
Aggregations
```

Analytics must clearly distinguish calculated metrics from stored business
facts.

---

# 35. Calculated Metrics

Calculated metrics should have explicit definitions.

Example:

```
Attendance Percentage
  =
Attended Eligible Sessions
/
Applicable Sessions
```

The exact formula must follow Attendance business rules.

Reports must not independently redefine such calculations.

---

# 36. Data Freshness

Reports should indicate whether their data represents:

```
Real-Time / Current
Near-Real-Time
Periodic Snapshot
```

The implementation mechanism will be decided during architecture/API design.

---

# 37. Reporting Performance

Heavy analytical queries should not unnecessarily degrade transactional
operations.

The implementation may later use:

```
Optimized Queries
Database Views
Materialized Views
Reporting Tables
Caching
```

only where justified by performance requirements.

---

# 38. Reporting Data Model

The Reports Module should prefer:

```
Views
Query Services
Aggregation Services
```

over duplicating transactional entities.

---

# 39. Materialized Reporting Data

If materialized reporting structures are required for performance, they
remain derived data.

The authoritative transactional source remains the owning business module.

---

# 40. Report Snapshot

For reports that need historical reproducibility, a snapshot mechanism may
be introduced.

This is a future design decision and is not currently frozen.

---

# 41. Report Scheduling

Future functionality may allow authorized users to schedule reports.

Examples:

```
Daily Attendance Report
Monthly Membership Report
Annual Governance Report
```

Scheduled-report functionality is not part of the current frozen scope.

---

# 42. Notifications

Reports may be delivered through the common Notification framework.

The Reports Module does not own notification infrastructure.

---

# 43. Search

Reports should provide controlled report discovery through:

```
Report Category
Report Name
Source Module
User Permission
```

---

# 44. Report Categories

Initial categories:

```
Membership
Attendance
Family
Governance
Youth
UPBS
```

Future categories may be added without redesigning the core reporting
architecture.

---

# 45. Cross-Module Data Integrity

When a report combines multiple modules, each source must be joined through
authoritative relationships.

Reports must not infer identity from display names when stable IDs are
available.

---

# 46. Person Identity

Cross-module reports should use the authoritative Person identity.

Person identity remains owned by the Person Module.

---

# 47. Membership Identity

Where membership-specific reporting is required, Reports shall use the
authoritative Membership identity.

---

# 48. Organization Identity

Organizational filtering shall use the authoritative Organization model.

Reports shall not create a duplicate organization hierarchy.

---

# 49. Governance Identity

Governance reporting shall use the authoritative Governance entities.

---

# 50. Attendance Identity

Attendance reporting shall use the authoritative Attendance identity and
business rules.

---

# 51. Family Identity

Family reporting shall use the authoritative Family model.

---

# 52. Youth Identity

Youth reporting shall use the authoritative Kumari/Kishor models as
applicable.

---

# 53. UPBS Identity

UPBS reporting shall use the authoritative UPBS records.

---

# 54. Report Access Boundary

The Reports Module is not an authorization bypass.

All report execution must pass through:

```
Authentication
    ↓
RBAC
    ↓
Organizational Scope
    ↓
Report Authorization
    ↓
Data Query
```

---

# 55. Sensitive Data

Reports may aggregate sensitive operational information.

Therefore:

```
Minimum Necessary Data
```

shall be exposed to each user.

---

# 56. No Business-State Mutation

Executing a report shall not modify the source transactional data.

Reports are read-oriented.

---

# 57. Exception

If a future reporting workflow includes an explicit approved action,
that action must be treated as a business transaction rather than an
ordinary report query.

---

# 58. Audit

The common Audit framework shall be used where report-related activities
require auditability.

Potential audit events include:

```
Report Configuration Change
Sensitive Report Access
Export
Scheduled Report Creation
Scheduled Report Modification
```

The exact audit catalogue remains to be finalized.

---

# 59. Error Handling

A report must clearly indicate when:

```
Data is unavailable
Source service is unavailable
Filters are invalid
User lacks authorization
Data is incomplete
```

The system must not present partial results as complete results without
appropriate indication.

---

# 60. Empty Results

A valid report with no matching records shall return an explicit empty
result rather than an error.

Example:

```
"No attendance records found for the selected period."
```

---

# 61. Report Parameters

Report parameters should be validated before query execution.

Invalid date ranges, organization scopes or unsupported filters must be
rejected.

---

# 62. Date Range Integrity

A report must not accept a date range that violates the report's supported
period definition.

---

# 63. Organization Scope Integrity

A user must not manipulate report filters to bypass organizational scope.

For example:

```
Sakha-level user
```

must not obtain:

```
Kendra-wide confidential report
```

by changing a URL parameter or filter.

---

# 64. Report Caching

Caching may be introduced for expensive reports.

Cached results must respect:

```
User Authorization
Organizational Scope
Data Freshness
```

---

# 65. Report Performance

Reports that operate over large datasets should be designed to avoid
unnecessary full-table scans.

Exact indexes and optimization strategies belong to database/API design.

---

# 66. Report Documentation

Each production report should document:

```
Purpose
Source Module
Data Fields
Filters
Calculation Rules
Visibility
Export Options
Refresh/Freshness
```

---

# 67. Traceability

Reports should maintain traceability to:

```
Business Requirement
    ↓
Source Module Rule
    ↓
Report Definition
    ↓
Implementation
    ↓
Test
    ↓
Release
```

This follows the project-wide requirement traceability principle.

---

# 68. No Duplicate Business Rules

The Reports Module shall not become a second location for Membership,
Attendance, Governance or UPBS business rules.

Where a metric depends on a source-module rule, the source-module rule is
authoritative.

---

# 69. Report Governance

New reports should follow the project's documentation and change-control
process.

A report shall not be added merely because a developer can technically
generate it.

---

# 70. Future Reporting Areas

The architecture should allow future report categories such as:

```
Sevak Reports
Publications Reports
Heritage Reports
Mahila Reports
Administration Reports
Finance Reports
Event Reports
```

These are future expansion areas unless separately approved.

---

# 71. Core Architectural Model

```text
Authoritative Modules
        │
        ├── Membership
        ├── Attendance
        ├── Family
        ├── Governance
        ├── Youth
        └── UPBS
                │
                ▼
        Reporting Layer
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
     Reports Dashboards Analytics
        │       │        │
        └───────┼────────┘
                ▼
             Export
```

---

# 72. Ownership Model

| Area                   | Owner               |
| ---------------------- | ------------------- |
| Membership Data        | Membership          |
| Attendance Data        | Attendance          |
| Family Data            | Family              |
| Governance Data        | Governance          |
| Youth Data             | Youth Modules       |
| UPBS Data              | UPBS                |
| Report Definitions     | Reports             |
| Report Execution       | Reports             |
| Analytics Presentation | Reports             |
| Export                 | Reports             |
| Authorization          | Central RBAC        |
| Audit                  | Common Audit        |
| Notifications          | Common Notification |

---

# 73. Initial Report Families

```text
Reports & Analytics
│
├── Membership
│
├── Attendance
│
├── Family
│
├── Governance
│
├── Youth
│
└── UPBS
```

---

# 74. No API Design Yet

This document does not define:

```
REST endpoints
Request/response schemas
Pagination contracts
Authentication headers
API versioning
```

Those belong to the later API design stage.

---

# 75. No Functional UI Design Yet

This document does not define final report screens or dashboard layouts.

UI design follows:

```
Business Rules
Table/Reporting Architecture
API Design
```

---

# 76. No SQL Yet

No PostgreSQL reporting views, materialized views or reporting tables are
frozen by this document.

Those decisions will follow the detailed reporting architecture and table
design.

---

# 77. Important Reporting Principle

Reports are a **consumer of authoritative data, not another system of
record**.

```text
Source Module
     │
     ▼
Authoritative Data
     │
     ▼
Reports & Analytics
```

---

# 78. Current Status

Reports & Analytics is now defined at the module-scope level.

Initial frozen report families:

```
Membership
Attendance
Family
Governance
Youth
UPBS
```

The detailed report catalogue, reporting data architecture, business rules,
and table/view design remain to be documented.

---

# 79. Source Alignment

The project module hierarchy explicitly places Reports & Analytics as a
dedicated module and identifies its initial scope as:

```
Membership Reports
Attendance Reports
Family Reports
Governance Reports
Youth Reports
UPBS Reports
```



The frozen top-level module hierarchy includes Reports as a separate module
with its own Django application:

```
backend/apps/reports
```



---

# 80. Status

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
