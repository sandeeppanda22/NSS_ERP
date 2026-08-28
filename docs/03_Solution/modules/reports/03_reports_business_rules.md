# NSS ERP — Reports & Analytics Business Rules

**Document ID:** SOL-RPT-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Reports & Analytics
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the Reports & Analytics
Module.

Reports & Analytics is a cross-module reporting and analytical capability.

It consumes authoritative data from business modules and shall not replace
those modules as systems of record.

---

# 2. Rule Classification

Rules in this document are classified as:

- FROZEN — explicitly established by approved project/source material
- SOURCE-ALIGNED — directly consistent with established architecture and
  project standards
- PENDING — requires explicit business approval
- FUTURE — outside the currently frozen scope

---

# 3. Reporting Ownership

## RPT-BR-001 — Reports Is a Separate ERP Module

**Status:** FROZEN

Reports & Analytics shall remain a dedicated ERP module.

The project module hierarchy explicitly identifies Reports & Analytics as a
separate module and Django application:

    backend/apps/reports

The initial reporting scope includes:

    Membership
    Attendance
    Family
    Governance
    Youth
    UPBS

---

## RPT-BR-002 — Reports Does Not Own Transactional Data

**Status:** SOURCE-ALIGNED

Reports shall not become the system of record for:

    Person
    Membership
    Attendance
    Family
    Governance
    Youth
    UPBS

The respective business modules remain authoritative.

---

## RPT-BR-003 — Source-of-Truth Principle

**Status:** SOURCE-ALIGNED

Every report shall derive its business facts from the authoritative source
module.

Example:

    Membership Report
        → Membership

    Attendance Report
        → Attendance

    Governance Report
        → Governance

---

# 4. Initial Reporting Scope

## RPT-BR-004 — Membership Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on Membership data.

Initial areas may include:

    Member Count
    Membership Type
    Membership Status
    Membership Year
    Renewal
    Transfer
    Organizational Distribution

The detailed report catalogue remains pending.

---

## RPT-BR-005 — Attendance Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on Attendance data.

Initial areas may include:

    Attendance Summary
    Member Attendance
    Sangha Attendance
    Attendance Percentage
    Attendance Trends
    Period-wise Attendance

Attendance business rules remain owned by Attendance.

---

## RPT-BR-006 — Family Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on Family data.

Initial areas may include:

    Family Count
    Family Size
    Family Composition
    Family Distribution
    Family Participation

Family business rules remain owned by Family.

---

## RPT-BR-007 — Governance Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on Governance data.

Initial areas may include:

    Current Office Holders
    Historical Office Holders
    Body Composition
    Position Assignments
    Acting Positions
    Vacancies
    Election Results

Governance remains authoritative.

---

## RPT-BR-008 — Youth Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on Youth-related modules.

This may include:

    Kumari Sangha
    Kishor Puja
    Youth Participation
    Youth Activities
    Youth-to-Membership Transition

The underlying Youth rules remain owned by the relevant Youth modules.

---

## RPT-BR-009 — UPBS Reporting

**Status:** FROZEN — SCOPE

Reports shall support reporting on UPBS data.

Possible areas include:

    Registration
    Delegate
    Prasad
    Accommodation
    Participation
    Committee
    Event Statistics

The detailed UPBS report catalogue remains pending.

---

# 5. Reporting Data Ownership

## RPT-BR-010 — Membership Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume Membership records.

Reports shall not create a duplicate membership master.

---

## RPT-BR-011 — Attendance Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume Attendance records and Attendance-defined
calculations.

Reports shall not independently redefine Attendance eligibility,
attendance identity, or attendance rules.

---

## RPT-BR-012 — Family Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume Family records.

No duplicate Family master shall be created.

---

## RPT-BR-013 — Governance Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume Governance records.

In particular, Governance reports must use the authoritative unified
Governance model.

---

## RPT-BR-014 — Youth Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume Youth records from the applicable Youth modules.

Reports shall not merge or redefine the business identity of Kumari and
Kishor merely for reporting convenience.

---

## RPT-BR-015 — UPBS Ownership

**Status:** SOURCE-ALIGNED

Reports shall consume UPBS records.

UPBS remains authoritative for UPBS-specific business rules.

---

# 6. No Duplicate Business Rules

## RPT-BR-016 — Source Business Rules Remain Authoritative

**Status:** SOURCE-ALIGNED

Reports shall not create a second interpretation of a source module's
business rule.

Example:

If Attendance defines how attendance percentage is calculated, Reports
must use that definition.

---

## RPT-BR-017 — Calculated Metrics

**Status:** SOURCE-ALIGNED

A calculated metric must have an identifiable business definition.

Examples:

    Attendance Percentage
    Renewal Rate
    Membership Growth
    Participation Rate

The underlying business rule must come from the authoritative source where
applicable.

---

# 7. Cross-Module Reporting

## RPT-BR-018 — Cross-Module Reports

**Status:** SOURCE-ALIGNED

Reports may combine information from multiple modules.

Examples:

    Person + Membership + Family

    Membership + Attendance

    Membership + Governance

    Family + Youth

    Membership + UPBS

---

## RPT-BR-019 — Stable Identity

**Status:** SOURCE-ALIGNED

Cross-module reports shall use authoritative stable identifiers.

Display names shall not be used as the primary identity mechanism when a
stable identifier is available.

---

## RPT-BR-020 — No Identity Duplication

**Status:** SOURCE-ALIGNED

Reports shall not create a second Person, Membership, Family or Organization
identity merely to simplify reporting.

---

# 8. Organizational Scope

## RPT-BR-021 — Scope-Aware Reporting

**Status:** SOURCE-ALIGNED

Reports shall respect the user's authorized organizational scope.

Possible organizational scopes include:

    Sakha
    Anchalika
    Zilla
    Kendra

---

## RPT-BR-022 — Scope Cannot Be Bypassed

**Status:** SOURCE-ALIGNED

A report filter shall never allow a user to bypass organizational
authorization.

Changing:

    URL parameter
    Query parameter
    Filter
    Request payload

must not expose unauthorized organizational data.

---

## RPT-BR-023 — Organization Is Authoritative

**Status:** SOURCE-ALIGNED

Reports shall use the authoritative Organization hierarchy.

Reports shall not create a duplicate:

    Kendra
    Anchalika
    Zilla
    Sakha

hierarchy.

The project-wide organizational governance standard requires organizational
relationships to remain traceable through the approved hierarchy.

---

# 9. RBAC

## RPT-BR-024 — Central RBAC

**Status:** SOURCE-ALIGNED

Reports shall use the central ERP RBAC framework.

Reports shall not create a separate permission architecture.

---

## RPT-BR-025 — Report Access Requires Authorization

**Status:** SOURCE-ALIGNED

A report shall be executed only after the applicable authorization checks.

Logical flow:

    Authentication
        ↓
    RBAC
        ↓
    Organizational Scope
        ↓
    Report Authorization
        ↓
    Report Query

---

## RPT-BR-026 — Governance Position Is Not Report Permission

**Status:** SOURCE-ALIGNED

Holding a governance position does not automatically grant access to every
report.

For example:

    President
    Secretary
    Treasurer

are Governance positions, not automatically report permissions.

---

# 10. Member-Facing Reports

## RPT-BR-027 — Member Report Access

**Status:** PENDING

Members may receive reports relating to:

    Their Own Information
    Approved Family Information
    Approved Attendance Information
    Approved Participation Information

The exact member-facing report catalogue and visibility rules require
explicit approval.

---

## RPT-BR-028 — Minimum Necessary Data

**Status:** SOURCE-ALIGNED

Member-facing reports shall expose only the data necessary for the approved
purpose.

---

# 11. Administrative Reporting

## RPT-BR-029 — Administrative Reports

**Status:** SOURCE-ALIGNED

Authorized administrative users may access broader reports according to:

    RBAC
    Organizational Scope
    Data Sensitivity

---

# 12. Governance Reporting

## RPT-BR-030 — Current Governance State

**Status:** SOURCE-ALIGNED

Current Governance reports shall use the current active governance
assignments.

---

## RPT-BR-031 — Historical Governance State

**Status:** SOURCE-ALIGNED

Historical Governance reports shall use preserved Governance assignment
history.

Example:

    Current President
    Historical President

must remain distinguishable.

---

## RPT-BR-032 — Election Results

**Status:** SOURCE-ALIGNED

Election reports shall use the authoritative Governance election results.

Reports shall not recalculate or replace the official election result.

---

# 13. Attendance Reporting

## RPT-BR-033 — Attendance Source Rule

**Status:** SOURCE-ALIGNED

Attendance reports shall use Attendance as the authoritative source.

---

## RPT-BR-034 — Attendance Calculation

**Status:** SOURCE-ALIGNED

Where Attendance defines a metric such as attendance percentage, Reports
shall use the approved Attendance calculation.

Reports shall not silently introduce a different denominator or eligibility
rule.

---

## RPT-BR-035 — Historical Attendance

**Status:** SOURCE-ALIGNED

Historical attendance must remain reportable where Attendance preserves the
underlying records.

---

# 14. Membership Reporting

## RPT-BR-036 — Current Membership

**Status:** SOURCE-ALIGNED

Current membership reports shall use the current authoritative Membership
state.

---

## RPT-BR-037 — Historical Membership

**Status:** SOURCE-ALIGNED

Historical membership reporting shall use preserved Membership history.

---

## RPT-BR-038 — Membership Year

**Status:** SOURCE-ALIGNED

Where a report is based on Membership Year, the definition of the Membership
Year shall come from Membership/business configuration rather than being
hard-coded separately in Reports.

---

# 15. Family Reporting

## RPT-BR-039 — Family Privacy

**Status:** SOURCE-ALIGNED

Family reports shall respect Family data visibility and authorization
rules.

---

## RPT-BR-040 — Family Composition

**Status:** SOURCE-ALIGNED

Family composition reports shall derive relationships from the authoritative
Family model.

Reports shall not independently infer family relationships from names or
other non-authoritative data.

---

# 16. Youth Reporting

## RPT-BR-041 — Youth Source Rules

**Status:** SOURCE-ALIGNED

Youth reports shall respect the business rules of the applicable Youth
module.

---

## RPT-BR-042 — Youth Identity

**Status:** SOURCE-ALIGNED

Youth reports shall use the authoritative Youth identity where applicable.

---

## RPT-BR-043 — Youth-to-Membership Transition

**Status:** SOURCE-ALIGNED

Where Youth modules record transition into NSS Membership, reports may
present that transition.

Reports shall not create or modify the transition.

---

# 17. UPBS Reporting

## RPT-BR-044 — UPBS Source of Truth

**Status:** SOURCE-ALIGNED

UPBS reports shall derive data from UPBS.

---

## RPT-BR-045 — UPBS Event Reporting

**Status:** SOURCE-ALIGNED

UPBS event reports may include:

    Registration
    Participation
    Accommodation
    Meal
    Delegate
    Prasad

where those source records exist and the user is authorized.

---

# 18. Report Filters

## RPT-BR-046 — Filter Validation

**Status:** SOURCE-ALIGNED

Report parameters must be validated before query execution.

---

## RPT-BR-047 — Date Range Validation

**Status:** SOURCE-ALIGNED

A report shall reject invalid date ranges.

Example:

    End Date < Start Date

must not produce a misleading report.

---

## RPT-BR-048 — Filter Applicability

**Status:** SOURCE-ALIGNED

Only filters applicable to a report should be accepted.

A Membership report should not silently accept an unrelated Governance
filter.

---

# 19. Time Periods

## RPT-BR-049 — Supported Periods

**Status:** SOURCE-ALIGNED

Reports may support:

    Day
    Week
    Month
    Quarter
    Year
    Membership Year
    Financial Year
    Governance Term

The exact period definitions are owned by the relevant business domain.

---

## RPT-BR-050 — No Independent Period Definition

**Status:** SOURCE-ALIGNED

Reports shall not independently redefine a source module's business period.

---

# 20. Historical Integrity

## RPT-BR-051 — History Never Deleted

**Status:** SOURCE-ALIGNED

Reporting must respect the project-wide principle that historical business
information is preserved.

---

## RPT-BR-052 — Current vs Historical

**Status:** SOURCE-ALIGNED

Reports shall distinguish current records from historical records.

---

# 21. Report Definition

## RPT-BR-053 — Report Identity

**Status:** PENDING

Each production report should have a stable:

    Report Code
    Report Name
    Description
    Source Module
    Category

The final report-definition table is to be finalized in REPORTS-04.

---

## RPT-BR-054 — Report Catalogue

**Status:** PENDING

The complete production report catalogue has not yet been frozen.

---

# 22. Report Categories

## RPT-BR-055 — Initial Categories

**Status:** FROZEN — SCOPE

Initial report categories are:

    Membership
    Attendance
    Family
    Governance
    Youth
    UPBS

---

## RPT-BR-056 — Future Categories

**Status:** FUTURE

Future report categories may include:

    Sevak
    Publications
    Heritage
    Administration
    Finance
    Events

No such category is frozen by this document.

---

# 23. Report Output

## RPT-BR-057 — Supported Output Formats

**Status:** SOURCE-ALIGNED

The reporting architecture may provide:

    On-Screen Report
    PDF
    Excel
    CSV

Availability depends on the individual report.

---

## RPT-BR-058 — Export Security

**Status:** SOURCE-ALIGNED

Exporting a report shall not provide greater access than viewing the same
report.

---

## RPT-BR-059 — Export Audit

**Status:** PENDING

The exact list of reports for which exports must be audited remains to be
approved.

---

# 24. Dashboard

## RPT-BR-060 — Dashboard Is Presentation

**Status:** SOURCE-ALIGNED

A dashboard is a presentation/analytics layer over authoritative data.

It does not become a second system of record.

---

## RPT-BR-061 — Dashboard Metrics

**Status:** SOURCE-ALIGNED

Dashboard KPIs must use approved metric definitions.

---

# 25. Report Calculations

## RPT-BR-062 — Calculation Transparency

**Status:** SOURCE-ALIGNED

Important calculated metrics should have documented definitions.

Example:

    Attendance Percentage

must have a documented numerator and denominator.

---

## RPT-BR-063 — No Silent Calculation Changes

**Status:** SOURCE-ALIGNED

A material change to a report calculation must be documented and traceable.

---

# 26. Reporting Data Freshness

## RPT-BR-064 — Freshness Disclosure

**Status:** PENDING

Where reporting data is not real-time, the report should communicate an
appropriate freshness/last-updated indicator.

The exact standard is not yet frozen.

---

# 27. Performance

## RPT-BR-065 — Protect Transactional Performance

**Status:** SOURCE-ALIGNED

Heavy analytical queries shall not unnecessarily degrade transactional
operations.

---

## RPT-BR-066 — Derived Reporting Structures

**Status:** PENDING

The system may use:

    Database Views
    Materialized Views
    Derived Reporting Tables
    Caching
    Read Replicas

where justified.

The project has not yet frozen which approach will be used.

---

# 28. No Premature Reporting Warehouse

## RPT-BR-067 — No Automatic Star Schema

**Status:** SOURCE-ALIGNED

The existence of Reports & Analytics does not by itself require a separate
data warehouse or star schema.

Such architecture requires explicit approval.

---

# 29. Report Read-Only Principle

## RPT-BR-068 — Reporting Does Not Mutate Business Data

**Status:** SOURCE-ALIGNED

Normal report execution shall be read-only.

A report must not:

    Change Membership
    Change Attendance
    Change Governance
    Change Family
    Change UPBS

---

# 30. Exceptions

## RPT-BR-069 — Explicit Business Action

**Status:** SOURCE-ALIGNED

If a future screen combines a report with a business action, the action must
be treated as a separate business transaction.

Example:

    Report → Review → Approve Correction

The approval is not itself a reporting operation.

---

# 31. Audit

## RPT-BR-070 — Common Audit Framework

**Status:** SOURCE-ALIGNED

Reports shall use the common Audit framework where reporting operations
require auditability.

Reports shall not create an independent audit mechanism.

---

# 32. Sensitive Reporting

## RPT-BR-071 — Sensitive Data

**Status:** SOURCE-ALIGNED

Reports containing sensitive information must be restricted according to
central security and authorization standards.

Potentially sensitive areas include:

    Personal Information
    Family Information
    Attendance
    Governance
    Administrative Information
    UPBS Information

---

# 33. Report Error Handling

## RPT-BR-072 — No Misleading Partial Results

**Status:** SOURCE-ALIGNED

If a report cannot retrieve all required source data, the system shall not
silently present an incomplete result as complete.

---

## RPT-BR-073 — Empty Result

**Status:** SOURCE-ALIGNED

A valid report with zero matching records shall return an explicit empty
result.

Example:

    No attendance records found for the selected period.

---

# 34. Report Traceability

## RPT-BR-074 — Requirement Traceability

**Status:** SOURCE-ALIGNED

Production reports shall be traceable through the project lifecycle:

    Requirement
        ↓
    Source Business Rule
        ↓
    Report Definition
        ↓
    Implementation
        ↓
    Test
        ↓
    Release

The project governance standards establish traceability as a mandatory
principle.

---

# 35. Report Change Management

## RPT-BR-075 — Controlled Report Changes

**Status:** SOURCE-ALIGNED

Changes to a production report's:

    Business Meaning
    Calculation
    Source
    Visibility
    Filters

must follow the project change-control process.

---

# 36. Report Versioning

## RPT-BR-076 — Report Definition Versioning

**Status:** PENDING

Where a report's business definition changes materially, the project should
retain sufficient version information to understand historical outputs.

The exact implementation is pending.

---

# 37. Scheduled Reports

## RPT-BR-077 — Scheduled Reporting

**Status:** FUTURE

Scheduled report delivery is not currently part of the frozen scope.

Future capability may support:

    Daily Reports
    Weekly Reports
    Monthly Reports
    Annual Reports

---

# 38. Report Notifications

## RPT-BR-078 — Common Notification Framework

**Status:** SOURCE-ALIGNED

Future report notifications should use the common Notification framework.

Reports shall not create a separate notification system.

---

# 39. Report Security Flow

## RPT-BR-079 — Authorization Before Data Access

**Status:** SOURCE-ALIGNED

The logical security sequence is:

    Authentication
        ↓
    RBAC
        ↓
    Organizational Scope
        ↓
    Report Authorization
        ↓
    Data Query

Authorization must be applied before unrestricted report data is returned.

---

# 40. Data Minimization

## RPT-BR-080 — Minimum Necessary Reporting

**Status:** SOURCE-ALIGNED

A report should expose only the information required for its approved
purpose.

---

# 41. No Display-Name Joins

## RPT-BR-081 — Stable Identity Joins

**Status:** SOURCE-ALIGNED

Cross-module joins should use stable identifiers.

The following should not be treated as authoritative identity:

    Person Name
    Sakha Name
    Family Name
    Position Name

when stable IDs exist.

---

# 42. Reporting and Organization

## RPT-BR-082 — Organizational Hierarchy

**Status:** SOURCE-ALIGNED

Reports shall respect the authoritative organizational hierarchy.

The project organizational standard establishes a single statutory
organizational root and requires traceable parent-child relationships.

---

# 43. Reporting and Governance

## RPT-BR-083 — Governance Authority

**Status:** SOURCE-ALIGNED

Reports shall not infer governance authority from arbitrary database
records.

Governance authority comes from the authoritative Governance model and
applicable governing rules.

---

# 44. Reporting and Membership

## RPT-BR-084 — Membership Authority

**Status:** SOURCE-ALIGNED

Reports shall not determine membership validity independently.

Membership remains authoritative.

---

# 45. Reporting and Attendance

## RPT-BR-085 — Attendance Authority

**Status:** SOURCE-ALIGNED

Reports shall not determine whether an attendance record is valid.

Attendance remains authoritative.

---

# 46. Reporting and Family

## RPT-BR-086 — Family Authority

**Status:** SOURCE-ALIGNED

Reports shall not infer family relationships independently.

Family remains authoritative.

---

# 47. Reporting and Youth

## RPT-BR-087 — Youth Authority

**Status:** SOURCE-ALIGNED

Reports shall not modify Youth records or reinterpret Youth lifecycle rules.

---

# 48. Reporting and UPBS

## RPT-BR-088 — UPBS Authority

**Status:** SOURCE-ALIGNED

Reports shall not modify UPBS transactions through ordinary report
execution.

---

# 49. Physical Reporting Model

## RPT-BR-089 — Physical Architecture Not Yet Frozen

**Status:** PENDING

The following options remain open:

    Direct PostgreSQL Views
    Materialized Views
    Reporting Tables
    Query Services
    Aggregation Services
    Hybrid Architecture

The final choice shall be based on performance, data freshness, historical
requirements and implementation complexity.

---

# 50. No API Yet

## RPT-BR-090 — API Design Deferred

**Status:** FROZEN PROJECT PROCESS

API contracts shall be designed after the database/reporting architecture
has been sufficiently defined.

This document does not freeze:

    REST endpoints
    Request schemas
    Response schemas
    Pagination
    API filters
    API versioning

---

# 51. No Functional UI Yet

## RPT-BR-091 — UI Design Deferred

**Status:** FROZEN PROJECT PROCESS

Functional report and dashboard UI design shall follow the documentation,
data and API design stages.

---

# 52. No SQL Yet

## RPT-BR-092 — SQL Deferred

**Status:** FROZEN PROJECT PROCESS

No PostgreSQL reporting views, materialized views or reporting tables are
frozen by this document.

---

# 53. Pending Decisions

The following remain explicitly pending:

    Complete Report Catalogue
    Member-Facing Report Visibility
    Detailed Export Permissions
    Report Freshness Standard
    Report Definition Versioning
    Report Execution History
    Dashboard Persistence
    Scheduled Reports
    Physical Reporting Architecture
    Materialized View Strategy
    Reporting Snapshot Strategy
    Detailed Sensitive-Report Matrix

---

# 54. Rule Summary

| Area | Status |
|---|---|
| Reports as Separate Module | FROZEN |
| Initial Report Scope | FROZEN |
| Source-of-Truth Principle | SOURCE-ALIGNED |
| No Duplicate Transactional Data | SOURCE-ALIGNED |
| Cross-Module Reporting | SOURCE-ALIGNED |
| Organizational Scope | SOURCE-ALIGNED |
| Central RBAC | SOURCE-ALIGNED |
| Historical Reporting | SOURCE-ALIGNED |
| Read-Only Reporting | SOURCE-ALIGNED |
| Membership Reporting | FROZEN — SCOPE |
| Attendance Reporting | FROZEN — SCOPE |
| Family Reporting | FROZEN — SCOPE |
| Governance Reporting | FROZEN — SCOPE |
| Youth Reporting | FROZEN — SCOPE |
| UPBS Reporting | FROZEN — SCOPE |
| Complete Report Catalogue | PENDING |
| Member Report Visibility | PENDING |
| Export Audit Matrix | PENDING |
| Data Freshness Standard | PENDING |
| Physical Reporting Architecture | PENDING |
| Scheduled Reports | FUTURE |
| Reporting Warehouse | FUTURE / NOT FROZEN |

---

# 55. Core Reporting Principle

The Reports & Analytics Module is:

    A consumer of authoritative data

not:

    Another system of record.

The architectural relationship is:

```text
Authoritative Business Modules
            ↓
      Reporting Layer
            ↓
     Reports / Analytics
            ↓
   Dashboard / Export
```

---

# 56. Source Alignment

The project module hierarchy establishes Reports & Analytics as a separate
module and identifies the initial reporting scope as:

```
Membership
Attendance
Family
Governance
Youth
UPBS
```

The project organizational governance standard establishes that
organizational structures must remain statutorily governed and
traceable through the approved hierarchy. Reports must therefore consume,
rather than redefine, that hierarchy.

---

# 57. Status

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
