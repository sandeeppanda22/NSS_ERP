# NSS ERP — Authentication & Security Business Rules

**Document ID:** SOL-AUTH-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business and security rules governing
authentication, account security, password security, and the security
boundary between authentication and authorization.

---

# 2. Rule Classification

Rules are classified as:

- FROZEN — explicitly established by the project source
- SOURCE-ALIGNED — directly supported by project standards
- PENDING — requires further approval
- FUTURE — outside the current frozen scope

---

# 3. Authentication Boundary

## AUTH-BR-001 — Authentication Establishes Identity

**Status:** FROZEN

Authentication shall establish that the user attempting to access the ERP
is the identity associated with the authenticated account.

---

## AUTH-BR-002 — Authentication and Authorization Are Separate

**Status:** FROZEN

Authentication answers:

    Who is the user?

Authorization answers:

    What may the user do?

Authentication shall not replace the centralized RBAC framework.

---

## AUTH-BR-003 — Successful Authentication Does Not Grant Global Access

**Status:** FROZEN

A successfully authenticated user shall not automatically receive access
to every ERP function.

Authorization shall subsequently evaluate:

    Role
    Permission
    Organizational Scope

---

# 4. User Account

## AUTH-BR-004 — Central User Account

**Status:** FROZEN

The ERP shall use the centralized:

    user_account

entity for authenticated ERP accounts.

---

## AUTH-BR-005 — Person Is Not User Account

**Status:** FROZEN

A Person and a User Account are distinct concepts.

A Person represents an individual in the ERP.

A User Account represents system-access capability.

---

## AUTH-BR-006 — User Account Does Not Create Membership

**Status:** FROZEN

Creating a User Account shall not automatically create:

    Membership
    Sangha Sevi ID
    Regular Membership
    Probationary Membership
    Associate Membership

Membership remains owned by the Membership Module.

---

## AUTH-BR-007 — User Account Does Not Create Person

**Status:** FROZEN

Authentication shall use the authoritative Person identity architecture.

It shall not create duplicate Person records.

---

# 5. Account Lifecycle

## AUTH-BR-008 — Account Lifecycle

**Status:** SOURCE-ALIGNED

User accounts shall support controlled lifecycle management.

Conceptually:

    Created
       ↓
    Active
       ↓
    Inactive / Locked
       ↓
    Retired

The exact status catalogue remains pending.

---

## AUTH-BR-009 — Account Deactivation

**Status:** SOURCE-ALIGNED

A deactivated account shall not be permitted to authenticate normally.

---

## AUTH-BR-010 — Deactivation Does Not Delete History

**Status:** FROZEN

Deactivating a user account shall not delete:

    Person
    Membership
    Business Records
    Audit History
    Historical Actions

---

## AUTH-BR-011 — Historical Attribution

**Status:** SOURCE-ALIGNED

Historical actions must remain attributable to the user who performed them,
even if that account later becomes inactive.

---

# 6. Password Security

## AUTH-BR-012 — Password Hashing

**Status:** FROZEN

Passwords shall never be stored as plaintext.

The project security baseline requires secure password hashing.

---

## AUTH-BR-013 — Argon2 Password Hashing

**Status:** FROZEN

The project security architecture identifies:

    Argon2 Passwords

as the approved password-hashing principle.

The implementation shall use the approved framework/security configuration
for Argon2 password hashing.

---

## AUTH-BR-014 — Password History

**Status:** FROZEN

Password history shall be maintained through:

    password_history

where required by the password-security model.

---

## AUTH-BR-015 — Password History Is Not Current Credential

**Status:** SOURCE-ALIGNED

Password history shall not be treated as the user's current authentication
credential.

---

## AUTH-BR-016 — Password History Preservation

**Status:** SOURCE-ALIGNED

Password-history records shall be protected from ordinary deletion.

---

# 7. Password Policy

## AUTH-BR-017 — Password Policy

**Status:** PENDING

The current project source does not freeze the complete password-policy
catalogue.

The following remain pending:

    Minimum Password Length
    Complexity Requirements
    Password Expiry
    Password Reuse Count
    Password Change Frequency

---

## AUTH-BR-018 — Password Reuse

**Status:** PENDING

The exact number of previous passwords that may not be reused has not been
frozen.

The existence of `password_history` provides the database foundation for
such a rule.

---

# 8. Password Reset

## AUTH-BR-019 — Password Reset

**Status:** PENDING

The current source does not define a complete password-reset workflow.

Any future reset mechanism must preserve authentication security and
auditability.

---

## AUTH-BR-020 — Password Recovery

**Status:** PENDING

The current source does not freeze a complete account-recovery mechanism.

No recovery workflow shall be implemented as a security bypass.

---

# 9. Authentication Failures

## AUTH-BR-021 — Failed Authentication

**Status:** SOURCE-ALIGNED

Authentication failures shall not expose unnecessary security information.

The exact failure-response mechanism is a technical/API decision.

---

## AUTH-BR-022 — Account Enumeration Protection

**Status:** PENDING

The exact mechanism for preventing account enumeration has not been frozen.

The implementation should avoid revealing whether a particular account
exists through authentication-error responses.

---

# 10. Account Locking

## AUTH-BR-023 — Account Lockout

**Status:** PENDING

The current source does not freeze:

    Maximum Failed Attempts
    Lockout Duration
    Automatic Unlock
    Administrator Unlock

These require separate security approval.

---

# 11. Session Security

## AUTH-BR-024 — Session Management

**Status:** FROZEN

Session Management is an established project security standard.

Authenticated sessions shall therefore be controlled and secured.

---

## AUTH-BR-025 — Session Termination

**Status:** SOURCE-ALIGNED

A user's authenticated session shall be capable of termination through
logout or security expiration.

---

## AUTH-BR-026 — Session Expiration

**Status:** PENDING

The exact session timeout is not frozen.

No fixed timeout is declared by this document.

---

## AUTH-BR-027 — Concurrent Sessions

**Status:** PENDING

The current source does not establish whether multiple simultaneous
sessions are permitted.

---

# 12. JWT Authentication

## AUTH-BR-028 — JWT Authentication

**Status:** FROZEN

The project security standard identifies:

    JWT Authentication

as part of the platform security architecture.

The exact token lifecycle and API implementation remain technical-design
concerns.

---

## AUTH-BR-029 — Token Security

**Status:** SOURCE-ALIGNED

Authentication tokens shall be protected against unauthorized disclosure
and reuse.

---

## AUTH-BR-030 — Token Expiration

**Status:** PENDING

The exact JWT access-token and refresh-token lifetime has not been frozen.

---

# 13. Authorization Boundary

## AUTH-BR-031 — Central RBAC

**Status:** FROZEN

Authorization shall use the centralized ERP RBAC framework.

The authorization foundation includes:

    role_master
    permission_master
    role_permission
    user_role
    admin_scope

---

## AUTH-BR-032 — No Authentication-Specific RBAC

**Status:** FROZEN

Authentication shall not create a second role or permission architecture.

Administration/RBAC remains authoritative.

---

## AUTH-BR-033 — Role Assignment

**Status:** SOURCE-ALIGNED

User-to-role assignments are represented through:

    user_role

---

## AUTH-BR-034 — Permission Assignment

**Status:** SOURCE-ALIGNED

Role-to-permission relationships are represented through:

    role_permission

---

# 14. Organizational Scope

## AUTH-BR-035 — Scope-Aware Authorization

**Status:** FROZEN

Where required, effective authorization shall consider organizational
scope.

Known scope levels are:

    KENDRA
    ANCHALIKA
    ZILLA
    SAKHA

---

## AUTH-BR-036 — Organization Is Authoritative

**Status:** FROZEN

Authentication shall not create or modify the organizational hierarchy.

Organization remains the authoritative source for organizational structure.

---

## AUTH-BR-037 — Scope Does Not Change Identity

**Status:** SOURCE-ALIGNED

Changing organizational scope does not create a new Person or User Account.

---

# 15. Sensitive Information

## AUTH-BR-038 — Sensitive Data Protection

**Status:** FROZEN

Sensitive data shall be appropriately protected.

The project security baseline identifies:

    Encrypted Sensitive Data

as a security principle.

---

## AUTH-BR-039 — Aadhaar Protection

**Status:** FROZEN

The project database/security architecture identifies:

    Aadhaar Encryption

as a security principle.

Aadhaar shall not be treated as an ordinary unprotected application field.

---

## AUTH-BR-040 — Credential Data Protection

**Status:** FROZEN

Credential-related information shall not be exposed through normal business
APIs, reports, or user-facing screens.

---

# 16. API Security

## AUTH-BR-041 — Backend Authorization

**Status:** SOURCE-ALIGNED

Authentication and authorization shall be enforced on the backend/API.

UI restrictions alone shall not constitute security.

---

## AUTH-BR-042 — API Authentication

**Status:** SOURCE-ALIGNED

Protected API endpoints shall require authenticated access where applicable.

---

## AUTH-BR-043 — API Authorization

**Status:** SOURCE-ALIGNED

Protected operations shall evaluate the appropriate:

    Permission
    Organizational Scope

after authentication.

---

## AUTH-BR-044 — No UI-Only Security

**Status:** SOURCE-ALIGNED

Hiding a button or menu item shall never be considered sufficient
authorization enforcement.

---

# 17. Module Access

## AUTH-BR-045 — Common Authentication

**Status:** FROZEN

All protected ERP modules shall use the common Authentication framework.

Modules shall not create independent login systems.

---

## AUTH-BR-046 — Common Authorization

**Status:** FROZEN

All protected ERP modules shall use the common authorization framework.

---

## AUTH-BR-047 — Sevak Example

**Status:** FROZEN

The Sevak Module uses:

    Existing ERP RBAC
    +
    Organizational Scope

and does not create a separate Sevak permission architecture.

---

# 18. Audit

## AUTH-BR-048 — Security Auditability

**Status:** SOURCE-ALIGNED

Important security and administrative events shall be auditable.

Examples include:

    Account Creation
    Account Deactivation
    Password Changes
    Role Changes
    Scope Changes
    Permission Changes

---

## AUTH-BR-049 — Central Audit

**Status:** FROZEN

Authentication & Security shall use the common Audit framework.

It shall not create a separate security-audit architecture.

---

## AUTH-BR-050 — Historical Security State

**Status:** SOURCE-ALIGNED

Security history shall remain traceable even when current security state
changes.

---

# 19. Account Changes

## AUTH-BR-051 — Role Change Does Not Rewrite History

**Status:** SOURCE-ALIGNED

Changing a user's current role shall not alter historical records of actions
performed under the previous authorization state.

---

## AUTH-BR-052 — Scope Change Does Not Rewrite History

**Status:** SOURCE-ALIGNED

Changing a user's organizational scope shall not retroactively alter
historical activity.

---

## AUTH-BR-053 — Password Change Does Not Erase History

**Status:** SOURCE-ALIGNED

Password changes shall not destroy the historical password-security record
where retained through `password_history`.

---

# 20. Least Privilege

## AUTH-BR-054 — Least Privilege

**Status:** SOURCE-ALIGNED

Users shall receive only the access required for their authorized
responsibilities.

---

# 21. Account Sharing

## AUTH-BR-055 — Shared Accounts

**Status:** PENDING

The current source does not provide a formal shared-account policy.

A production security policy should explicitly determine whether shared
accounts are prohibited and how exceptional technical accounts are handled.

---

# 22. Administrator Security

## AUTH-BR-056 — Authentication Does Not Grant Administrative Privilege

**Status:** FROZEN

Logging into the ERP does not automatically make a user an administrator.

Administrative access is controlled by the centralized RBAC framework.

---

## AUTH-BR-057 — Administrator Self-Escalation

**Status:** PENDING

The current source does not freeze a complete mechanism preventing an
administrator from granting themselves additional privileges.

This requires a separate security/segregation-of-duties decision.

---

# 23. Security Configuration

## AUTH-BR-058 — Configuration Over Hardcoding

**Status:** SOURCE-ALIGNED

Security-related configurable values should be centrally configured rather
than scattered through application code.

Examples include:

    Token Lifetime
    Session Timeout
    Lockout Threshold
    Password Policy

where such settings are approved.

---

# 24. Encryption

## AUTH-BR-059 — Encryption of Sensitive Data

**Status:** SOURCE-ALIGNED

Sensitive information shall use the approved encryption mechanism where
encryption at rest is required.

The exact encrypted-field catalogue is pending detailed security design.

---

# 25. Database Security

## AUTH-BR-060 — Database Integrity

**Status:** SOURCE-ALIGNED

The database shall enforce structural integrity through:

    Primary Keys
    Foreign Keys
    Unique Constraints
    Appropriate CHECK Constraints

where applicable.

---

## AUTH-BR-061 — Row-Level Security

**Status:** SOURCE-ALIGNED

The project architecture identifies:

    RLS

as a database security principle.

The exact tables and policies requiring RLS must be finalized during detailed
database/security design.

---

# 26. Soft Delete

## AUTH-BR-062 — Historical Preservation

**Status:** SOURCE-ALIGNED

Applicable security/account records shall follow the project-wide history
preservation and soft-delete principles.

The project standard identifies:

    is_active
    deleted_at
    deleted_by_sangha_sevi_pk

for applicable records.

---

# 27. Physical Deletion

## AUTH-BR-063 — No Uncontrolled Physical Delete

**Status:** FROZEN

Security/account history shall not be physically deleted through ordinary
business operations where doing so would destroy historical accountability.

---

# 28. Security Event Logging

## AUTH-BR-064 — Security Events

**Status:** PENDING

The current source does not freeze a dedicated security-event table.

If detailed security-event storage is required, it must be approved before
adding a new table.

---

# 29. Login History

## AUTH-BR-065 — Login History

**Status:** PENDING

The current frozen schema does not include:

    login_history

Authentication logging requirements shall be handled through the approved
Audit/security architecture unless a dedicated table is later approved.

---

# 30. MFA

## AUTH-BR-066 — Multi-Factor Authentication

**Status:** PENDING

The current source does not freeze MFA as a database or business
requirement.

No:

    mfa_configuration

table is introduced by this baseline.

---

# 31. Trusted Devices

## AUTH-BR-067 — Trusted Device Management

**Status:** PENDING

The current source does not freeze trusted-device functionality.

No dedicated device table is introduced.

---

# 32. Password Reset Tables

## AUTH-BR-068 — Password Reset Data Model

**Status:** PENDING

The current source does not freeze:

    password_reset
    password_reset_token

as database tables.

---

# 33. Account Lockout Tables

## AUTH-BR-069 — Account Lockout Data Model

**Status:** PENDING

The current source does not freeze a separate account-lockout table.

---

# 34. Session History Tables

## AUTH-BR-070 — Session History Data Model

**Status:** PENDING

The project security standard requires session management, but it does not
freeze a separate:

    session_history

table.

---

# 35. Authentication Tables

## AUTH-BR-071 — Current Frozen Security Foundation

**Status:** FROZEN

The current security foundation contains:

    user_account
    password_history
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

Total:

    7 tables

---

# 36. Table Ownership

## AUTH-BR-072 — Authentication Tables

**Status:** FROZEN

Authentication & Security directly owns the authentication/account-security
concepts:

    user_account
    password_history

---

## AUTH-BR-073 — RBAC Tables

**Status:** FROZEN

Administration/RBAC owns the authorization-management concepts:

    role_master
    permission_master
    role_permission
    user_role
    admin_scope

Authentication consumes the resulting authorization state.

---

# 37. No Duplicate Security Architecture

## AUTH-BR-074 — Single Security Foundation

**Status:** FROZEN

NSS ERP shall maintain one common Authentication & Security foundation.

Modules shall not create independent authentication mechanisms.

---

# 38. Authentication Failure Information

## AUTH-BR-075 — Minimize Security Disclosure

**Status:** SOURCE-ALIGNED

Authentication responses should not unnecessarily disclose:

    Whether an account exists
    Password validity details
    Internal account state
    Security configuration

Exact response wording is an API implementation concern.

---

# 39. Security Credentials in Logs

## AUTH-BR-076 — No Credential Leakage

**Status:** SOURCE-ALIGNED

Passwords, password hashes, authentication secrets, and equivalent sensitive
credentials shall not be written to ordinary application logs.

---

# 40. Tokens in Logs

## AUTH-BR-077 — No Authentication Token Leakage

**Status:** SOURCE-ALIGNED

Authentication tokens and equivalent security credentials shall not be
written to ordinary logs.

---

# 41. Security and Development

## AUTH-BR-078 — Production Credentials

**Status:** SOURCE-ALIGNED

Production credentials and secrets shall not be embedded in source code.

---

# 42. Security and Testing

## AUTH-BR-079 — Security Testing

**Status:** SOURCE-ALIGNED

Authentication and authorization behaviour shall be tested before release.

Tests shall cover at minimum:

    Valid Authentication
    Invalid Authentication
    Unauthorized Access
    Authorized Access
    Scope Restriction

The complete security test catalogue remains to be defined.

---

# 43. Security and Release

## AUTH-BR-080 — Security Before Production

**Status:** SOURCE-ALIGNED

Authentication/security changes shall be verified before production
deployment.

---

# 44. Core Security Model

```text
Person / Identity
        │
        ▼
   user_account
        │
        ▼
 Authentication
        │
        ▼
Authenticated User
        │
        ├──────────────┐
        ▼              ▼
      Role           Scope
        │              │
        ▼              ▼
   Permission     Organization
        │              │
        └──────┬───────┘
               ▼
      Effective Authorization
               │
               ▼
        Business Operation
```

---

# 45. Rule Summary

| Area                                | Status         |
| ----------------------------------- | -------------- |
| Authentication establishes identity | FROZEN         |
| Authentication ≠ Authorization      | FROZEN         |
| Central User Account                | FROZEN         |
| Person ≠ User Account               | FROZEN         |
| Passwords not plaintext             | FROZEN         |
| Argon2 password hashing             | FROZEN         |
| Password History                    | FROZEN         |
| JWT Authentication                  | FROZEN         |
| Session Management                  | FROZEN         |
| Central RBAC                        | FROZEN         |
| Organizational Scope                | FROZEN         |
| Sensitive Data Encryption           | FROZEN         |
| Aadhaar Encryption                  | FROZEN         |
| Central Audit                       | FROZEN         |
| Least Privilege                     | SOURCE-ALIGNED |
| API Authorization                   | SOURCE-ALIGNED |
| Account Lockout Policy              | PENDING        |
| Password Policy                     | PENDING        |
| Password Reset                      | PENDING        |
| Session Timeout                     | PENDING        |
| Concurrent Sessions                 | PENDING        |
| MFA                                 | PENDING        |
| Trusted Devices                     | PENDING        |
| Login History Table                 | PENDING        |
| Security Event Table                | PENDING        |
| Administrator Self-Escalation       | PENDING        |
| Shared Accounts                     | PENDING        |

---

# 46. Core Principle

The central Authentication & Security rule is:

```
Securely authenticate the correct identity,
protect credentials and security state,
and then apply centralized authorization.
```

---

# 47. Source Alignment

The project security standards explicitly identify:

```
RBAC
JWT Authentication
Password Hashing
Encrypted Sensitive Data
Audit Logging
Session Management
```

as security standards.

The platform architecture additionally identifies:

```
UUID Internal PKs
Business IDs
Aadhaar Encryption
Argon2 Passwords
RBAC
RLS
Immutable Audit
Soft Delete
```

as database/security principles.

The current PostgreSQL security foundation contains exactly:

```
user_account
password_history
role_master
permission_master
role_permission
user_role
admin_scope
```

The detailed schema therefore remains bounded to these seven tables unless
new requirements are formally approved.

---

# 48. Status

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
