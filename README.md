# NSS ERP

Nilachala Saraswata Sangha Enterprise Resource Planning (NSS ERP)

---

# Overview

NSS ERP is a comprehensive web-based management platform being developed for Nilachala Saraswata Sangha.

The system is designed to support membership management, family management, governance, attendance tracking, Kumari Sangha, Kishor Puja, Founder & Heritage records, UPBS operations, reporting, and future NSS operational activities.

The project follows a:

```text
Database First
    ↓
API First
    ↓
UI First
```

design philosophy, ensuring that business rules are frozen before implementation.

---

# Project Objectives

* Centralized NSS member management
* Family-first relationship tracking
* Governance and committee management
* Attendance and review workflows
* Kumari Sangha and Kishor Puja management
* Founder & Heritage preservation
* UPBS operational support
* Historical record preservation
* Audit-compliant data management
* Role-based access control
* International branch support

---

# Technology Stack

> **Note:** `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` is the Approved
> forward-looking decision record — it replaces Bootstrap 5 with Tailwind CSS +
> DaisyUI + Alpine.js, commits to actually wiring up FastAPI, and adds a hosting/offline plan.
> None of that is implemented in code yet; the stack below reflects the current codebase.

## Frontend

* Django Templates
* Bootstrap 5
* HTMX *(dependency pinned via `django-htmx`; not yet wired into any template as of the current codebase — see `docs/PROJECT_DOCUMENTATION.md` → Gotchas)*

---

## Backend

* Django
* FastAPI *(pinned in `requirements.txt`; no FastAPI app/router exists in `backend/` yet — Django views call the ORM directly, see `docs/PROJECT_DOCUMENTATION.md` → Architecture)*

---

## Database

* PostgreSQL

---

## Authentication

* Django Authentication
* JWT (Future)

---

## Deployment

* Ubuntu
* Nginx
* Gunicorn

---

## Future Enhancements

* Redis Cache
* Background Workers
* Mobile Application
* API Integrations

---

# Project Architecture

```text
Browser
   │
   ▼
Django Templates
   │
   ▼
Django Views (function-based; call the ORM directly)
   │
   ▼
Django ORM
   │
   ▼
PostgreSQL
```

*(Note: FastAPI is pinned as a dependency but has no app/router wired up yet — the diagram
above reflects the actual current request path. See `docs/PROJECT_DOCUMENTATION.md` →
Architecture for the planned two-track Django ORM / raw-SQL-DDL data layer.)*

---

# Core Principles

## Person ≠ Member

A Person may exist without being a Member.

Examples:

* Family Member
* Kumari Participant
* Kishor Participant
* Future Applicant
* Historical Person

A Member must always be a Person.

---

## Family First

Family relationships are maintained independently of membership status.

---

## History Never Deleted

Business records are preserved permanently.

Physical deletion is avoided.

Soft delete is preferred.

---

## Audit First

All critical business operations must be auditable.

---

## Master Data Driven

Business configuration is controlled through master tables rather than hardcoded values.

---

## Global Ready

The system is designed to support NSS activities within India and internationally.

---

# Organization Hierarchy

```text
KENDRA
├── ANCHALIKA
│   └── SAKHA
├── ZILLA
│   └── SAKHA
└── PATHA_CHAKRA
```

Notes:

* PATHA_CHAKRA is an Organization Type.
* PATHA_CHAKRA exists directly under KENDRA.
* PATHA_CHAKRA may operate within India or internationally.
* SAKHA exists under ANCHALIKA or ZILLA.

> **Open:** the Organization module's business rules (v1.1.0, GOVERNANCE ALIGNED,
> `docs/03_Solution/modules/organization/04_organization_business_rules.md`) explicitly leave
> the type-to-type parent compatibility matrix shown above as an **open item**, not a frozen
> decision — only the generic apex + self-referencing 3-table structure is frozen. Treat this
> diagram as the current working assumption, not a closed design.

> **Frozen separately:** an **8-type inventory** — the 5 types in the diagram above, plus
> `NILACHALA_KUTIRA` and `SMRUTI_MANDIRA` (both unique, fixed-code, not shown here since they
> don't participate in the parent hierarchy) and `SAKHA_ASANA` (sequence-generated like `SAKHA`,
> not yet placed in this diagram — its own parent relationship is part of the still-open matrix
> above). This is a type-*inventory* freeze only, separate from the still-open parent-matrix
> question.

> **Open:** the generic 3-table structure is implemented in SQL, but the seeded
> `organization_type_master` rows use `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`/`SAKHA_SANGHA` as their
> business codes, not the short `ANCHALIKA`/`ZILLA`/`SAKHA` forms shown in the diagram above. See
> `docs/PROJECT_DOCUMENTATION.md` → Open questions / TODOs.

---

# Module Structure

*The sections below describe the full planned module roadmap. Currently only
**Foundation, Membership, Family, Governance (stub), Attendance (stub), and Founder & Heritage**
exist as Django apps under `backend/` — Mahila Sangha, Kumari Sangha, Kishor Puja, Sevak
Sangha, UPBS, Reports & Analytics, Administration, Audit, Backup & Technical, Finance,
Programmes & Events, and Assets & Property have no app directory yet. Solution-layer design
documentation (overview/ERD/lifecycle/business-rules/table-design) is complete for essentially
every module on this roadmap — ahead of, and not yet reconciled with, any backend
implementation. **Programmes & Events is the one exception**: still DRAFT, explicitly not
frozen, though its cross-module reconciliation gates are closed and its candidate table set has
settled. Two modules (Foundation, Authentication & Security) share a name with an existing
`backend/` app but design an unrelated schema — see `docs/PROJECT_DOCUMENTATION.md` → Gotchas.
See `docs/PROJECT_DOCUMENTATION.md` for the current, code-verified status of each.*

## Foundation

* Organization Management
* Person Management
* Master Data
* Authentication & RBAC
* Audit & History
* Global Location Management

---

## Membership

* Member Registration
* Membership Types
* Membership Approval
* Renewal
* Transfer
* Membership Journey
* Sangha Sevi ID Management

---

## Family

* Family Dashboard
* Family Tree
* Relationship Management

---

## Governance

* General Body
* Governing Body
* Advisory Board
* Committees
* Position Assignment

---

## Attendance

* Weekly Attendance
* Attendance Review
* Attendance Reports

---

## Mahila Sangha

* Membership
* Activities
* Governance

---

## Kumari Sangha

* KM Identity
* Activities
* Training
* Membership Transition

---

## Kishor Puja

* KH Identity
* Registration
* Guardian Assignment

---

## Sevak Sangha

* Volunteer Development
* Training
* Activities

---

## Founder & Heritage

* Biography
* Philosophy
* Teachings
* Publications

---

## UPBS

* Registration
* Accommodation
* Committee Management
* Reports

---

## Reports & Analytics

* Membership Reports
* Attendance Reports
* Governance Reports
* UPBS Reports

---

## Administration

* Users
* Roles
* Permissions
* System Settings

---

# Database Design Principles

## Person Module

```text
Person ≠ Member
```

A Person may exist without Membership.

A Member must always be linked to a Person.

---

## Contact Information

Supports:

* International Phone Numbers
* Country Phone Codes
* Email Addresses

Rules:

* Mobile Number + Country Phone Code must be unique.
* Email is not required to be unique.
* At least one contact method is mandatory.

---

## Address Management

Supports:

* Multiple Addresses
* Primary Address Selection
* Global Locations
* Postal Code Mapping

Rules:

* One Person may have multiple addresses.
* Only one address may be Primary.
* Primary Address may be changed at any time.

---

## Location Hierarchy

```text
Country
    ↓
State / Province
    ↓
District / Region
    ↓
City / Village
```

Postal Codes are maintained separately and linked through mapping tables.

---

# Development Workflow

## Branch Strategy

```text
main
 └── develop
      └── feature/*
```

---

## Feature Development Workflow

```text
Create Feature Branch
        ↓
Implement Changes
        ↓
Commit Changes
        ↓
Merge into develop
        ↓
Create Release Notes
        ↓
Create Git Tag
        ↓
Merge develop into main
        ↓
Create GitHub Release
```

---

# Release Management

Every version must include:

* Git Tag
* Release Notes Document
* GitHub Release

Release Notes Location:

```text
docs/05_Releases/
```

Examples:

```text
v0.1.0.md
v0.2.0.md
v0.2.1.md
v0.3.0.md
v0.4.0.md
v0.5.0.md
v0.5.1.md
```

---

# Completed Milestones

## v0.1.0

Initial Project Setup

---

## v0.2.0

Foundation Models

---

## v0.2.1

Admin Setup

---

## v0.3.0

UI Foundation and Authentication Complete

---

## v0.4.0

Organization Module Design Complete *(design/ERD/business-rules/table-design docs only — see
v0.5.1+ and Current Development Status below for the later SQL implementation)*

---

## v0.5.0

Person Module Design Complete

---

## v0.5.1

Person Database Schema Complete

* Global Location Model
* Person Schema
* Person Address Schema
* International Mobile Support
* Address Mapping Model

---

# Current Development Status

Completed:

* Foundation Architecture
* Authentication Foundation
* Organization Module Design (v1.1.0, GOVERNANCE ALIGNED; type-to-type parent hierarchy left as
  an open item, not frozen)
* Person Module Design (v1.0.0, SOURCE ALIGNED — 1 table: `person`; `document_master` is owned
  by Foundation, see below)
* Person Database Schema (partial — `person`/`person_address` implemented; the docs' `person_id`
  naming doesn't match the DDL's `person_code`)
* Foundation Database Schema ("Foundation Vertical Slice" — 12 tables + full seed data under
  `database/ddl/01_foundation/`/`database/seed/01_foundation/` — still zero Django code)
* Organization Database Schema ("Organization Vertical Slice" — 3 tables
  (`organization_type_master`, `organization_status_master`, `organization`) + full seed data
  under `database/ddl/02_organization/`/`database/seed/02_organization/`, matching the frozen
  generic structure exactly — still zero Django code. Combined with Foundation and Bootstrap
  RBAC: **18 tables implemented** — see `database/README.md`)
* Bootstrap RBAC DDL (`role_master`/`permission_master`/`role_permission`, `SOL-BOOT-001`/
  `SOL-ARCH-011` — DDL implemented and committed; `role_master` seeded with 8 roles,
  the other two empty pending the permission catalogue; ownership stays with Administration,
  see `docs/PROJECT_DOCUMENTATION.md` → Gotchas for a role-catalogue discrepancy this surfaced)
* Global Location Model
* Membership Module Design
* Family Module Design
* Attendance Module Design (Review Workflow Frozen)
* Founder & Heritage Module Design (v1.0.0, SOURCE ALIGNED — 8 tables designed; backend
  implements only 1, `founder_master`)
* Kumari Sangha Module Design (v1.0.0, SOURCE ALIGNED)
* Kishor Puja Module Design (v1.0.0, SOURCE ALIGNED — Guardian Model frozen v2.1)
* Mahila Sangha Module Design (v2.1.0, Bye-Law-aligned governance model)
* Sevak Sangha Module Design (partially frozen — table design only; see
  `docs/PROJECT_DOCUMENTATION.md`)
* Foundation Module Design (v1.0.0, SOURCE ALIGNED — describes 10 tables: the original 8
  master-data/geography/sequence tables plus `document_master` + `field_change_log`; same name,
  different scope from the `backend/foundation/` Django app). **SQL implements 12 tables** (2
  more than the design doc covers — see Foundation Database Schema above and
  `docs/PROJECT_DOCUMENTATION.md`)
* Administration Module Design (v1.0.0, SOURCE ALIGNED — 8 Administration-owned tables: 5 RBAC
  tables plus the Correspondence Register; `user_account`/`password_history` are exclusively
  Authentication-owned)
* Authentication & Security Module Design (v1.0.0, SOURCE ALIGNED — exclusively owns
  `user_account`+`password_history`; references but doesn't own Administration's 5 RBAC tables;
  different schema from the real `backend/authentication/` app)
* Governance Module Design (v1.0.0, SOURCE ALIGNED — Unified Body Governance Model + Elections,
  9 tables; freezes the Mahila Parichalana Mandali term at 3 years, conflicting with the Mahila
  module's own frozen 2-year term — unreconciled, see `docs/PROJECT_DOCUMENTATION.md`)
* Publications Module Design (v1.0.0, SOURCE ALIGNED + USER REQUIREMENTS — zero new tables,
  reuses Founder & Heritage's publication tables)
* UPBS Module Design (v1.0.0, SOURCE ALIGNED — 7 tables)
* Reports & Analytics Module Design (v1.0.0, SOURCE ALIGNED — 5 metadata/config-only tables)
* Audit Module Design (v1.0.0, SOURCE ALIGNED — 2 tables)
* Backup & Technical Module Design (v1.0.0, SOURCE ALIGNED — 2 tables)
* Finance Module Design (v1.0.0, SOURCE ALIGNED — 7 tables: financial_year, financial_scope,
  fund_master, financial_transaction, financial_receipt, financial_payment, financial_transfer;
  derives from NSS Bye-Law Section F and Mahila Sangha Bye-Law Clause 7)
* Programmes & Events Module Design (Module #21, v0.1.0, DRAFT — NOT FROZEN — Programme Type →
  Event Instance two-level model; 7 candidate common tables, all cross-module reconciliation
  gates closed (`SOL-EVT-007`) but no table frozen DDL yet)
* Assets & Property Module Design (Module #22, v1.0.0, SOURCE ALIGNED — 7 tables: property,
  asset, custodianship, property_statutory_record, maintenance_record, property_document,
  asset_document; 74 business rules)

Current Focus:

* Reconciling Solution-layer design docs with actual Django/SQL implementation across all 22
  documented modules — every module now has a complete (or largely complete) design. Two
  modules have real SQL implementation (Foundation: 12 tables; Organization: 3 tables) — 15
  tables total, still zero corresponding Django code for either. No release doc has been
  created yet for either the module-documentation backlog or the Foundation/Organization SQL
  implementation.

Next Release Target:

```text
Not yet decided — the module-documentation backlog (organization through sevak) is now largely
complete at the design level, and backend/database implementation has begun on the SQL track
(Bootstrap RBAC + Foundation + Organization vertical slices, 18 tables total). No release has
been cut for either slice yet. See docs/PROJECT_DOCUMENTATION.md → Open questions / TODOs.
```

---

# Repository Structure

```text
NSS_ERP
│
├── backend
│
├── database
│   ├── ddl
│   ├── seed
│   └── scripts
│
├── docs
│   ├── 00_Project_Governance
│   ├── 01_Authoritative_References
│   ├── 02_Requirements
│   ├── 03_Solution
│   ├── 04_Testing
│   └── 05_Releases
│
├── CLAUDE.md
├── README.md
└── requirements.txt
```

See `docs/PROJECT_DOCUMENTATION.md` for the full, code-verified breakdown of each directory.

---

# Current Stable Version

```text
v0.5.1
```

Person Database Schema Complete

---

# License

Internal NSS ERP Project

All Rights Reserved.
