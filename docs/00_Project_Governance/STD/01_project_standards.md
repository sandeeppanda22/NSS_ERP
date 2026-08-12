# NSS ERP Project Standards

Version: 1.0

Status: FROZEN

---

# 1. Purpose

This document defines the standards governing the design, development, testing, deployment, and maintenance of the NSS ERP platform.

All project contributors must follow these standards.

---

# 2. Project Principles

The NSS ERP platform shall be guided by the following principles:

* Person ≠ Member
* Family First Model
* History Never Deleted
* Documentation First
* Configuration Over Hardcoding
* Master Data Driven
* Auditability
* Security by Design
* By-Law Supremacy
* Mobile Friendly
* Accessibility Focused

---

# 3. Technology Stack

## Database

PostgreSQL

## Backend

Django

FastAPI

## Frontend

Django Templates

Bootstrap 5

HTMX

## Development Tools

VS Code

Git

DBeaver

## Infrastructure

Ubuntu Linux

Docker

Nginx

---

# 4. Database Principles

## Primary Keys

All major business tables shall use UUID primary keys.

Example:

person_pk

family_group_pk

sangha_sevi_pk

---

## Business IDs

User-visible identifiers shall be separate from primary keys.

Examples:

P00000001

FG00000001

SS00000001

---

## Foreign Keys

Foreign keys shall always reference UUID primary keys.

Never reference business IDs.

---

## Soft Delete

Records shall not be physically deleted.

Use:

is_active

deleted_at

deleted_by_sangha_sevi_pk

---

# 5. Audit Principles

Every transactional table shall support:

created_at

created_by_sangha_sevi_pk

updated_at

updated_by_sangha_sevi_pk

deleted_at

deleted_by_sangha_sevi_pk

is_active

---

# 6. Security Principles

Role Based Access Control (RBAC)

Row Level Security (RLS)

Encrypted Sensitive Data

Secure Password Storage

Immutable Audit Logs

Principle of Least Privilege

---

# 7. Development Standards

All development shall occur through Git branches.

Direct commits to main are prohibited.

All changes must be reviewed before merging.

---

# 8. Documentation Standards

Business Rules First

Database Design Second

UI Design Third

Implementation Fourth

Testing Fifth

---

# 9. UI Standards

Responsive Design

Mobile Friendly

Simple Navigation

Minimal Training Requirement

Elder-Friendly Interface

Avoid Enterprise ERP Complexity

---

# 10. Testing Standards

Unit Testing

Integration Testing

User Acceptance Testing

Regression Testing

Security Testing

---

# 11. Deployment Standards

Development

UAT

Production

Environment separation is mandatory.

---

# 12. Change Management

All schema changes shall be version controlled.

All business rule changes shall be documented before implementation.

All major architectural decisions shall be recorded in project documentation.

---

# 13. Source Control Strategy

main

Production-ready code only.

develop

Integration branch.

feature/*

Module-specific development.

---

# 14. Project Workflow

Business Rules
↓
Documentation
↓
Database Design
↓
Schema Review
↓
Implementation
↓
Testing
↓
Deployment

This workflow is mandatory for all NSS ERP modules.
