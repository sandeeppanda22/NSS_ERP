# NSS ERP — Authentication & Security Module Overview

**Document ID:** SOL-AUTH-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Authentication & Security Module provides the centralized security
foundation for NSS ERP.

Its responsibilities include:

    Authentication
    Account Security
    Password Security
    Identity Verification
    Secure Session Access
    Security Controls

Authorization management through:

    Roles
    Permissions
    Organizational Scope

is centrally managed through the Administration/RBAC framework.

---

# 2. Module Boundary

Authentication & Security answers:

    Who is the user?
    Can the user authenticate?
    Is the account allowed to authenticate?
    Is the authentication credential valid?

Administration/RBAC answers:

    What may the authenticated user do?
    Within what organizational scope?

Therefore:

```text
Authentication & Security
        │
        ▼
Authenticated User
        │
        ▼
Administration / RBAC
        │
        ▼
Effective Authorization
```

---

# 3. Current Frozen Security Foundation

The current project schema review identifies exactly seven tables in the
Authentication & Security foundation:

```
user_account
password_history

role_master
permission_master
role_permission
user_role

admin_scope
```

Total:

```
7 tables
```

---

# 4. Responsibility Boundary

The seven tables are logically divided as follows.

## Authentication / Account Security

```
user_account
password_history
```

## Authorization / RBAC

```
role_master
permission_master
role_permission
user_role
admin_scope
```

The authorization portion is administered through the centralized
Administration/RBAC capability.

---

# 5. Authentication

Authentication establishes the identity of the person attempting to access
the ERP.

Conceptually:

```text
User
 │
 ▼
Authentication Request
 │
 ▼
Credential Verification
 │
 ▼
Authenticated Session
```

---

# 6. User Account

`user_account` represents the ERP account used for authentication.

It is not a replacement for the Person entity.

Conceptually:

```text
Person
  │
  ▼
User Account
  │
  ▼
Authentication
```

The authoritative Person identity remains owned by the Person/Identity
architecture.

---

# 7. Person vs User Account

The project follows:

```
Person ≠ User Account
```

A Person may exist without having an ERP login account.

A user account exists to provide system access to an authorized identity.

---

# 8. User Account vs Membership

The following concepts remain separate:

```
Person
User Account
Membership
Sangha Sevi ID
```

A user account does not automatically create:

```
Membership
Sangha Sevi ID
```

Membership remains owned by the Membership Module.

---

# 9. Password Security

The Authentication & Security foundation includes:

```
password_history
```

Password security is therefore part of the centralized security architecture.

---

# 10. Password History

`password_history` provides the historical password-security foundation.

It exists separately from the current authentication credential.

Its detailed lifecycle and password-policy rules require the subsequent
Business Rules and Table Design documents.

---

# 11. Password Protection

Passwords shall not be stored as plaintext.

The project technology baseline identifies secure password hashing as a
security requirement.

The exact implementation mechanism must follow the approved Authentication
technical design.

---

# 12. Credential Security

Authentication credentials are security-sensitive information.

They shall not be exposed through:

```
Normal API responses
User search
Member profile screens
Reports
Audit displays
```

unless explicitly required by an approved security function.

---

# 13. Authentication Failure

Authentication failures shall not reveal unnecessary information about
whether a particular account exists.

Detailed failure-response behaviour will be defined during API/security
design.

---

# 14. Account State

A user account may have an operational state such as:

```
Active
Inactive
Locked
```

The final account-state model requires detailed business-rule approval.

This overview does not freeze a final enumeration.

---

# 15. Account Deactivation

Deactivating an account shall prevent unauthorized future authentication.

It shall not delete:

```
Person
Membership
Business History
Audit History
```

associated with the user.

---

# 16. Historical Accountability

A deactivated account may remain associated with historical actions.

The system must not destroy historical accountability merely because an
account is no longer active.

---

# 17. Authentication vs Authorization

Authentication:

```text
Who are you?
```

Authorization:

```text
What can you do?
```

The two responsibilities shall remain separate.

---

# 18. RBAC Dependency

After successful authentication, the user enters the centralized RBAC
framework.

Conceptually:

```text
Authentication
      │
      ▼
user_account
      │
      ▼
Administration / RBAC
      │
      ├── user_role
      ├── role_master
      ├── role_permission
      ├── permission_master
      └── admin_scope
```

---

# 19. No Duplicate RBAC

Authentication & Security shall not create another permission system
separate from Administration.

The centralized RBAC model remains authoritative.

---

# 20. Role Management Boundary

`role_master` is part of the centralized security/RBAC foundation.

Detailed management of roles belongs to Administration.

Authentication consumes the resulting authorization state.

---

# 21. Permission Management Boundary

`permission_master` defines application permissions.

Administration centrally manages the permission catalogue.

Authentication does not independently define business permissions.

---

# 22. User Role Boundary

`user_role` represents assignment of application roles to users.

The relationship is part of the centralized RBAC model.

Authentication uses the resulting roles after successful authentication.

---

# 23. Organizational Scope Boundary

`admin_scope` represents organizational authorization scope.

Known levels include:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

The Organization Module remains authoritative for the organizational
hierarchy.

---

# 24. Security and Organization

Authentication does not create organizational units.

Administration uses the Organization hierarchy to determine applicable
scope.

Conceptually:

```text
Organization
      │
      ▼
Administrative Scope
      │
      ▼
Authorization
```

---

# 25. Security and Audit

Security-sensitive actions may require centralized auditability.

Examples include:

```
Account Creation
Account Deactivation
Password Security Changes
Authentication Security Events
Privilege Changes
```

The centralized Audit Module remains the audit authority.

---

# 26. No Duplicate Security Audit

Authentication & Security shall not create an independent:

```
security_audit
```

framework.

The common Audit framework shall be reused where applicable.

---

# 27. Session Security

Authenticated access requires controlled session handling.

The exact session mechanism is a technical implementation decision.

The module must ensure that authentication state cannot be casually reused
after:

```
Logout
Account Deactivation
Session Expiration
Security Revocation
```

where applicable.

---

# 28. Logout

A user shall be able to terminate their authenticated session.

The exact session invalidation mechanism is defined in the technical
implementation.

---

# 29. Session Expiration

Authenticated sessions should expire according to the approved security
policy.

The current source does not freeze a specific timeout duration.

Therefore no exact timeout is declared here.

---

# 30. Concurrent Sessions

The current source does not establish a final policy governing simultaneous
sessions from multiple devices.

This remains a pending security decision.

---

# 31. Account Lockout

The current source does not establish the exact failed-login threshold or
lockout duration.

Therefore the following are not frozen:

```
Maximum failed attempts
Lockout duration
Automatic unlock policy
Administrator unlock policy
```

These require detailed security rules.

---

# 32. Password Policy

The current source establishes password security as part of the platform
security architecture but does not provide the complete password-policy
catalogue.

The following remain pending:

```
Minimum length
Complexity requirements
Password expiry
Password reuse count
Reset frequency
Lockout interaction
```

---

# 33. Password Reuse

`password_history` provides the foundation for password-history management.

The exact number of previous passwords that cannot be reused is not frozen
by this overview.

---

# 34. Password Reset

Password-reset functionality may be required.

The current source does not freeze the complete reset workflow.

Any reset mechanism must preserve account security and auditability.

---

# 35. Account Recovery

Account-recovery mechanisms are security-sensitive.

The final workflow must not bypass authentication controls.

No specific recovery mechanism is frozen by this document.

---

# 36. Identity Verification

Authentication depends on an authoritative identity.

The existing Person architecture remains the source for person identity.

Authentication does not create a second Person record.

---

# 37. One Person, Multiple Accounts

The final policy for whether one Person may have multiple ERP accounts is not
frozen by the current source.

This requires an explicit security decision.

---

# 38. Account Ownership

A user account must remain attributable to its underlying identity.

Accounts shall not be casually shared between individuals.

The final shared-account policy requires detailed security rules.

---

# 39. Administrative Access

Administrative privileges are not granted merely because authentication
succeeds.

After authentication:

```text
Authenticated
      ↓
RBAC Evaluation
      ↓
Scope Evaluation
      ↓
Authorized / Denied
```

---

# 40. Least Privilege

The security architecture follows the principle of least privilege.

Users should receive only the permissions required for their authorized
responsibilities.

---

# 41. No UI-Only Security

Security shall not depend solely on hiding UI controls.

Backend/API operations must independently enforce authorization.

---

# 42. API Security

Authenticated APIs shall validate:

```
Authentication
Authorization
Organizational Scope
```

The exact API mechanism will be defined in the API design stage.

---

# 43. Sensitive Data

Authentication-related sensitive information must not be exposed through
ordinary application responses.

This includes credential-related information and security secrets.

---

# 44. Encryption

The project architecture identifies encryption of sensitive data as a
security principle.

The exact list of encrypted fields and encryption implementation must be
defined through the detailed Security design.

---

# 45. Aadhaar Security

The project architecture identifies Aadhaar encryption as a security
principle.

Aadhaar remains a sensitive identity/document concern and shall not be
treated as an authentication password.

The exact storage/encryption implementation belongs to the Identity
Document/Security design.

---

# 46. Business Identity vs Authentication Identity

The system must distinguish:

```text
Person Identity
       │
       ├── Membership Identity
       │
       └── User Account Identity
```

One does not automatically imply the creation of the others.

---

# 47. Membership Dependency

Membership remains independent from authentication.

For example:

```text
Person
  │
  ├── Member? → Membership
  │
  └── ERP User? → User Account
```

A person may therefore be represented in the system without necessarily
having an ERP login.

---

# 48. Authentication and Governance

Governance positions do not directly authenticate users.

A governance position may result in application permissions through the
central RBAC model.

---

# 49. Authentication and Administration

Administration manages:

```
Roles
Permissions
User Role Assignments
Organizational Scope
```

Authentication manages:

```
Credential Verification
Account Security
Authentication State
```

---

# 50. Authentication and Audit

Authentication/security events requiring auditability should be sent to the
central Audit framework.

Authentication does not create a separate audit repository.

---

# 51. Authentication and Notifications

Security workflows may require notifications, such as approved password
recovery or security alerts.

Where required, the common Notification framework shall be used.

Authentication does not create a separate notification engine.

---

# 52. Authentication and Documents

Authentication does not own identity-document storage.

The Document/Identity Document architecture remains responsible for
documents.

---

# 53. Account Deletion

Physical deletion of a user account must not be used in a way that destroys
historical accountability.

The final account-retirement strategy requires detailed security design.

---

# 54. Historical Preservation

Security history should remain traceable after:

```
Account Deactivation
Role Changes
Scope Changes
Password Changes
```

where applicable.

---

# 55. Current Frozen Security Tables

```text
user_account
password_history

role_master
permission_master
role_permission
user_role

admin_scope
```

Total:

```
7 tables
```

---

# 56. Ownership Boundary

## Authentication & Security

Owns:

```
Authentication
Account Security
Password Security
Security Controls
```

## Administration

Owns:

```
Roles
Permissions
Role Assignments
Administrative Scope
```

## Organization

Owns:

```
Organizational Hierarchy
```

## Person

Owns:

```
Person Identity
```

## Membership

Owns:

```
Membership Identity and Lifecycle
```

## Audit

Owns:

```
Centralized Audit History
```

---

# 57. Tables Not Assumed

This overview does not introduce:

```
login_history
session_history
account_lockout
password_reset
authentication_token
security_event
mfa_configuration
trusted_device
user_security_profile
```

These require explicit approved requirements before becoming part of the
database foundation.

---

# 58. Security Configuration Boundary

Security configuration should follow the project's:

```
Configuration Over Hardcoding
```

principle.

Security constants and operational settings should not be scattered
throughout application code.

---

# 59. Security by Design

Security shall be considered throughout:

```
Database
API
Backend
UI
Infrastructure
Deployment
```

rather than being added only after implementation.

---

# 60. Infrastructure Dependency

The project technology architecture identifies:

```
PostgreSQL
Django
FastAPI
Docker
Nginx
Ubuntu
```

as part of the platform architecture.

Security controls must be implemented consistently across these layers.

---

# 61. Security and Database

Database-level controls should protect:

```
Credential data
Security relationships
Referential integrity
Sensitive identity data
```

Application authorization remains necessary in addition to database
integrity constraints.

---

# 62. Security and Deployment

Production deployment shall apply the approved security configuration.

Development credentials and production credentials must not be casually
shared.

The exact secrets-management architecture requires separate infrastructure
design.

---

# 63. Security and Auditability

The project follows the principle:

```
Important security changes must remain traceable.
```

Central Audit shall be used where the relevant event is designated as
auditable.

---

# 64. Current Architecture

```text
                       ┌─────────────────────┐
                       │      Person         │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │    user_account     │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       Authentication
                                  │
                                  ▼
                       Authenticated User
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
                  RBAC                     Scope
                     │                         │
                     ▼                         ▼
                 Role/Permission         Organization
                     │                         │
                     └────────────┬────────────┘
                                  ▼
                         Effective Access
                                  │
                                  ▼
                         Business Modules
```

---

# 65. Core Security Principle

The central Authentication & Security principle is:

```
Authenticate the correct identity securely,
protect credentials and security state,
then delegate authorization to the centralized RBAC framework.
```

---

# 66. Design Boundary

This overview establishes:

```
Authentication Boundary
Account Security Boundary
Password Security Boundary
RBAC Dependency
Organizational Scope Dependency
Audit Dependency
Person Identity Dependency
```

It does not yet freeze:

```
Password Policy
Lockout Policy
Session Timeout
Concurrent Session Policy
MFA
Password Reset Workflow
Account Recovery
Device Trust
Complete Authentication Event Catalogue
Secrets Management
Detailed Security API
```

---

# 67. Source Alignment

The authoritative schema review identifies the Authentication & Security
foundation as:

```
user_account
password_history
role_master
permission_master
role_permission
user_role
admin_scope
```

for a total of seven tables.

The project technology/security baseline also identifies:

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

as platform security principles.

The Administration/RBAC rules establish that authorization is centralized
and organizational-scope aware; Authentication & Security therefore remains
responsible for authentication rather than creating a second authorization
framework.

---

# 68. Status

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
