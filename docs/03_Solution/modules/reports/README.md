# NSS ERP Reports & Analytics Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0. Full Solution design complete (4 files); there is no
`backend/reports/` Django app.

---

## Documents

01_reports_module_overview.md (`SOL-RPT-001`) — Version 1.0.0
Purpose: Centralized reporting, analytical views, dashboards, summaries, and export
capabilities across NSS ERP.

02_reports_erd.md — Version 1.0.0 (functions as the reporting-architecture document)
Purpose: Entity relationship design for the metadata/configuration tables, and the "Report
Data → Authoritative Business Module" data-flow principle.

03_reports_business_rules.md — Version 1.0.0, RPT-BR-001–RPT-BR-092
Purpose: Business rules — organizational scope enforcement, central RBAC, History Never
Deleted applied to reporting configuration.

04_reports_table_design.md — Version 1.0.0
Purpose: Physical table design — five metadata/configuration tables.

---

## Key facts

- Cross-module read/analytics capability consuming authoritative data from Membership,
  Attendance, Family, Governance, Kumari/Kishor ("Youth"), and UPBS. Reports does **not** own
  or duplicate any transactional data from those modules.
- **Five tables, metadata/configuration only:** `report_category_master`,
  `report_definition`, `report_filter_definition`, `dashboard`, `dashboard_widget`.
- No premature star schema or data warehouse — Source-of-Truth principle: the business modules
  remain authoritative, Reports only configures how their data is presented.
- Physical reporting architecture (views vs. materialized views vs. derived tables)
  deliberately **not** frozen — "simplest reliable query first."
- Report execution, snapshotting, scheduling, and export persistence are all marked
  PENDING/FUTURE, not designed yet.

---

## Current Status

Design Complete · ERD/Architecture Complete · Business Rules Drafted (SOURCE ALIGNED) · Table
Design Drafted (metadata-only, SOURCE ALIGNED) · SQL Implementation Not Started ·
`backend/reports/` Django app does not exist yet
