# NSS ERP — Security Architecture

**Document ID:** SOL-SEC-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED (Cross-Reference)
**Scope:** Security Architecture Map
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document maps the security architecture of the NSS ERP by
identifying which existing document is authoritative for each security
concern.

It does not duplicate the rules already defined in those documents. It
establishes the ownership map so that:

- Security questions route to the correct authoritative source
- No two documents independently define the same security rule
- Gaps between documents are visible

---

# 2. Security Architecture Overview

```
Security Architecture
        │
        ├── Governance Security Standards
        │       └── 00_Project_Governance/STD/05_security_standards.md
        │
        ├── Authentication (Identity Verification)
        │       └── 03_Solution/modules/authentication/
        │
        ├── Authorization / RBAC (Access Control)
        │       └── 03_Solution/modules/administration/
        │
        ├── Administration (Role/Permission Management)
        │       └── 03_Solution/modules/administration/
        │
        ├── Audit (Change Tracking — Centralized)
        │       └── 03_Solution/modules/audit/
        │       (Per-table audit columns defined in DATABASE_DESIGN_STANDARDS.md)
        │
        ├── Data Security (Encryption, Sensitive Data)
        │       └── 00_Project_Governance/STD/05_security_standards.md (policy)
        │       └── Relevant module business/table-design rules (column-level)
        │       └── Authentication module (credential-specific security)
        │
        └── Module-Level Security Rules
                └── Each module's business rules document
```

---

# 3. Authoritative Document Map

| Security Concern | Authoritative Document | Document ID |
|-----------------|----------------------|-------------|
| Security principles, password policy, encryption standards, RLS principles | `00_Project_Governance/STD/05_security_standards.md` | STD-05 |
| User identity, credential storage, password hashing (Argon2), JWT, session management | `03_Solution/modules/authentication/` (4 files) | SOL-AUTH-001–004 |
| Role definitions, permission definitions, role-permission mapping, user-role assignment, organizational scope | `03_Solution/modules/administration/` (4 files) | SOL-ADM-001–004 |
| Audit trail, centralized audit records, system events | `03_Solution/modules/audit/` (4 files) | SOL-AUD-001–004 |
| Per-table audit metadata (created_by, updated_by, deleted_by) | `03_Solution/database/DATABASE_DESIGN_STANDARDS.md` | SOL-DB-001 |
| Sensitive data handling (Aadhaar, PII) | STD-05 (policy) + relevant module table designs (column-level) + Authentication (credential security) | STD-05 + SOL-AUTH + SOL-PER |
| Backup security, restore authorization | `03_Solution/modules/backup_technical/` (4 files) | SOL-BAK-001–004 |

---

# 4. Security Layer Responsibilities

## 4.1 Governance Layer (STD-05)

Defines project-wide security standards that all modules must follow:

- Password complexity and rotation policy
- Encryption requirements (at rest, in transit)
- Authentication protocol requirements
- Row-Level Security (RLS) principles
- Session security requirements
- Data classification levels

STD-05 sets policy; modules implement.

---

## 4.2 Authentication Layer

Owned by: Authentication Module

Frozen tables:

```
user_account
password_history
```

Responsibilities:

- Identity verification (who is this user?)
- Credential management (password storage, hashing)
- JWT token issuance and validation
- Session lifecycle
- Login/logout events

NOT responsible for: what a user can do (that is Authorization).

---

## 4.3 Authorization / RBAC Layer

Owned by: Administration Module

Frozen tables:

```
role_master
permission_master
role_permission
user_role
admin_scope
```

Responsibilities:

- Role definitions and hierarchy
- Permission definitions
- Role-to-permission mapping
- User-to-role assignment
- Organizational scope (which organizations a role applies to)

NOT responsible for: verifying identity (that is Authentication).

---

## 4.4 Audit Layer

Owned by: Audit Module

Frozen tables:

```
audit_master
system_event_log
```

Responsibilities:

- Centralized audit records and system event logging
- Audit trail integrity
- Non-repudiation

Complemented by: per-table audit columns (`created_by`, `updated_by`,
`deleted_by`) defined in the Database Design Standards. Transactional
tables retain standardized audit metadata independently of the
centralized Audit Module tables.

---

## 4.5 Module-Level Security

Each module's business rules define access patterns:

- Who can create/read/update/delete within that domain
- Domain-specific approval workflows
- Data visibility rules per role

These rules consume the RBAC framework — they do not independently
define permissions infrastructure.

---

# 5. Shared Table Ownership

`user_account` is physically defined once but logically shared:

| Module | Ownership Aspect |
|--------|-----------------|
| Authentication | Identity columns, credentials, hashing, session |
| Administration | Role assignment (`user_role` references `user_account`) |

This shared ownership is explicitly documented in both modules.

---

# 6. Security Boundary Rules

1. No module shall create its own authentication mechanism
2. No module shall create its own permission/role tables
3. No module shall create its own audit framework
4. All modules consume the common security infrastructure
5. Governance position (President, Parichalak) ≠ Application role
6. Geographic hierarchy ≠ Organizational scope boundary

---

# 7. What Is NOT Frozen

The following security elements are documented as requirements but not
yet frozen as tables:

```
login_history
session_history
mfa_configuration
password_reset_token
account_lockout
```

These exist in the Authentication business rules as future requirements.
They do not have frozen table designs.

---

# 8. Indicative Implementation Dependency Sequence

Security implementation follows the project's Database-First order.
Exact FK ordering remains open (see DATABASE_DESIGN_STANDARDS.md § 35).

```
1. Foundation DDL (id_sequence_master, masters)
2. Person DDL (person, document_master)
3. Organization DDL (organization tables)
4. Authentication DDL (user_account, password_history)
5. Administration DDL (RBAC tables — depends on Auth)
6. Audit DDL (audit_master, system_event_log)
7. Django security middleware
8. FastAPI security dependencies
9. Row-Level Security policies
10. UI authorization checks
```

---

# 9. Cross-Reference Summary

```
STD-05 (Policy)
   │
   │ implements
   ▼
Authentication Module ──────► WHO are you?
   │
   │ feeds identity to
   ▼
Administration Module ──────► WHAT can you do?
   │
   │ enforced by
   ▼
Per-Module Business Rules ──► Domain-specific access
   │
   │ recorded by
   ▼
Audit Module ───────────────► WHO did WHAT and WHEN?
```

---

# 10. Status

```
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED (Cross-Reference)

VERSION:
1.0.0
```

This document maps existing security architecture. It does not introduce
new security decisions or tables.

---

# End of Document
