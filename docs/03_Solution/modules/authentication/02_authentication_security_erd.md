# NSS ERP — Authentication & Security Entity Relationship Design

**Document ID:** SOL-AUTH-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
Authentication & Security foundation of NSS ERP.

The current source-supported security foundation contains:

    user_account
    password_history
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

Total:

    7 tables

No additional authentication/security tables are introduced by this ERD.

---

# 2. Responsibility Boundary

The security foundation is logically divided into:

## Authentication / Account Security

    user_account
    password_history

## Authorization / RBAC

    role_master
    permission_master
    role_permission
    user_role
    admin_scope

Administration is the operational owner of the RBAC management capability.

Authentication & Security remains responsible for authentication and
credential security.

---

# 3. High-Level ERD

```text
                         ┌──────────────────┐
                         │   user_account   │
                         └────────┬─────────┘
                                  │
                         ┌────────┴─────────┐
                         │                  │
                         ▼                  ▼
                ┌────────────────┐   ┌───────────────┐
                │password_history│   │   user_role   │
                └────────────────┘   └───────┬───────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │ role_master │
                                      └──────┬──────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │role_permission  │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │permission_master │
                                    └──────────────────┘

                         ┌──────────────────┐
                         │   admin_scope    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         Organization Hierarchy
```

---

# 4. `user_account`

## Purpose

Represents an ERP account used to authenticate an authorized identity.

---

## Primary Key

```text
user_account_pk
```

---

## Logical Relationships

`user_account` participates in:

```
Password History
User Role Assignment
Administrative Scope
```

Conceptually:

```text
user_account
     │
     ├── password_history
     │
     ├── user_role
     │
     └── admin_scope
```

The exact physical FK structure for every relationship is finalized in
Table Design.

---

# 5. Person Dependency

The user account is associated with an authoritative identity.

Conceptually:

```text
Person
   │
   ▼
user_account
   │
   ▼
Authentication
```

Person remains owned by the Person/Identity architecture.

Authentication does not create a duplicate Person table.

---

# 6. Person ≠ User Account

The ERD preserves the distinction:

```text
Person
   ≠
User Account
```

A Person may exist without an ERP login account.

---

# 7. Membership Boundary

The ERD does not connect `user_account` directly to Membership as an
authorization substitute.

Membership remains the authoritative source for membership identity and
status.

---

# 8. `password_history`

## Purpose

Represents historical password-security information associated with a user
account.

---

## Logical Relationship

```text
user_account
      │
      │ 1:N
      ▼
password_history
```

A user account may have multiple historical password records.

---

## Primary Key

The exact primary-key structure shall follow the final Authentication table
design.

No additional password-history tables are introduced here.

---

# 9. Password History Boundary

`password_history` records password history.

It does not represent:

```
Current User Identity
Membership
Role
Permission
Organizational Scope
```

---

# 10. Password Security

The ERD treats password history as part of Authentication & Security.

It does not introduce separate:

```
password_reset
password_policy
password_lockout
```

entities because those are not currently frozen by the source.

---

# 11. `role_master`

## Purpose

Represents reusable application authorization roles.

---

## Primary Key

```text
role_master_pk
```

---

## Logical Relationship

```text
user_account
      │
      ▼
user_role
      │
      ▼
role_master
```

---

# 12. `permission_master`

## Purpose

Represents centrally defined application permissions.

---

## Primary Key

```text
permission_master_pk
```

---

## Logical Relationship

```text
role_master
      │
      ▼
role_permission
      │
      ▼
permission_master
```

---

# 13. `role_permission`

## Purpose

Represents the relationship between roles and permissions.

---

## Primary Key

```text
role_permission_pk
```

---

## Relationship

```text
role_master
      1
      │
      N
role_permission
      N
      │
      1
permission_master
```

This is a normalized many-to-many relationship.

---

# 14. `user_role`

## Purpose

Represents assignment of application roles to user accounts.

---

## Primary Key

```text
user_role_pk
```

---

## Relationship

```text
user_account
      1
      │
      N
user_role
      N
      │
      1
role_master
```

---

# 15. `admin_scope`

## Purpose

Represents organizational authorization scope.

Known scope levels are:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

---

## Primary Key

```text
admin_scope_pk
```

---

# 16. Scope Relationship

Conceptually:

```text
user_account
      │
      ▼
admin_scope
      │
      ▼
Organization Unit
```

The exact physical FK between `admin_scope` and the Organization tables is
not frozen by the current source and will be finalized during Table Design.

---

# 17. Organization Dependency

Administration does not own the organizational hierarchy.

The Organization module remains authoritative.

Conceptually:

```text
Organization
      │
      ▼
Organizational Hierarchy
      │
      ▼
admin_scope
      │
      ▼
Authorization
```

---

# 18. Scope Levels

The logical scope model is:

```text
KENDRA
   │
   ▼
ANCHALIKA
   │
   ▼
ZILLA
   │
   ▼
SAKHA
```

This represents the known organizational authorization levels.

The statutory organizational hierarchy remains authoritative.

---

# 19. Effective Authorization

The logical authorization model is:

```text
User
 +
Role
 +
Permission
 +
Organizational Scope
        ↓
Effective Authorization
```

---

# 20. Complete Authorization Flow

```text
                         ┌─────────────────┐
                         │  user_account   │
                         └────────┬────────┘
                                  │
                     ┌────────────┼────────────┐
                     │            │            │
                     ▼            ▼            ▼
              password_history  user_role  admin_scope
                                  │            │
                                  ▼            ▼
                             role_master   Organization
                                  │
                                  ▼
                           role_permission
                                  │
                                  ▼
                         permission_master
                                  │
                                  └──────┬─────┘
                                         ▼
                                Effective Access
```

---

# 21. Authentication Flow

The logical authentication flow is:

```text
Person / Identity
       │
       ▼
user_account
       │
       ▼
Credential Verification
       │
       ▼
Authenticated User
       │
       ▼
RBAC Evaluation
       │
       ▼
Scope Evaluation
       │
       ▼
Authorized / Denied
```

---

# 22. Authentication vs Authorization

Authentication establishes identity.

Authorization establishes access.

Therefore:

```text
Authentication
      ↓
Who?
      ↓
Authenticated User
      ↓
Authorization
      ↓
What?
      ↓
Effective Access
```

---

# 23. No Duplicate Authentication Entity

The ERD does not introduce:

```
admin_user
login_user
technical_user
```

as alternative identity entities.

`user_account` remains the account-level identity for ERP authentication.

---

# 24. No Duplicate RBAC Entity

The ERD does not introduce:

```
authentication_role
authentication_permission
```

The common RBAC entities remain:

```
role_master
permission_master
role_permission
user_role
```

---

# 25. User-to-Role Relationship

```text
user_account
     │
     │ 1:N
     ▼
user_role
     │
     │ N:1
     ▼
role_master
```

This allows reusable roles to be assigned to multiple users.

---

# 26. Role-to-Permission Relationship

```text
role_master
     │
     │ 1:N
     ▼
role_permission
     │
     │ N:1
     ▼
permission_master
```

This allows permissions to be reused across multiple roles.

---

# 27. User-to-Permission Derivation

There is no need for a direct:

```text
user_permission
```

table in the current frozen model.

Effective permissions are derived through:

```text
user_account
     ↓
user_role
     ↓
role_master
     ↓
role_permission
     ↓
permission_master
```

---

# 28. Scope-Aware Authorization

Permissions may be scope-sensitive.

Conceptually:

```text
User
 │
 ├── Permission
 │
 └── Scope
       │
       ▼
Organization Boundary
```

Therefore the same permission may produce different effective access
depending on the user's authorized organizational scope.

---

# 29. No Duplicate Organization Hierarchy

The ERD does not introduce:

```
admin_kendra
admin_anchalika
admin_zilla
admin_sakha
```

Organization remains the authoritative source of organizational structure.

---

# 30. Governance Position Boundary

Governance positions are not represented as RBAC roles by default.

For example:

```
President
Secretary
Parichalak
```

belong to Governance.

Application roles belong to Administration/RBAC.

Any mapping between the two requires explicit design.

---

# 31. Membership Boundary

Membership statuses are not represented as RBAC roles.

For example:

```
Regular Member
Probationary Member
Associate Member
```

remain Membership concepts.

---

# 32. Audit Boundary

Security-sensitive changes may generate Audit events.

Conceptually:

```text
Authentication/Security Change
        │
        └── Audit Event

Role Change
        │
        └── Audit Event

Permission Change
        │
        └── Audit Event

Scope Change
        │
        └── Audit Event
```

The Audit Module remains the centralized audit authority.

---

# 33. No Security Audit Table

The current ERD does not introduce:

```
security_audit
```

or:

```
authentication_audit
```

tables.

---

# 34. Historical Integrity

Changes to current security state shall not rewrite historical audit
information.

Examples:

```
Password Change
Role Change
Scope Change
Account Deactivation
```

must remain historically attributable where auditability is required.

---

# 35. Account Lifecycle

The ERD supports the concept of an account lifecycle without introducing
additional lifecycle tables.

Conceptually:

```text
Account Created
      ↓
Active
      ↓
Inactive / Locked
      ↓
Retired
```

The exact lifecycle statuses remain pending.

---

# 36. Password Lifecycle

The relationship is:

```text
user_account
      │
      └──< password_history
```

Each relevant password change may produce a historical password record.

The exact password-policy workflow remains pending.

---

# 37. Role Lifecycle

The relationship is:

```text
user_account
      │
      └──< user_role >── role_master
```

The current ERD does not introduce a dedicated role-history table.

---

# 38. Permission Lifecycle

The relationship is:

```text
role_master
      │
      └──< role_permission >── permission_master
```

The current ERD does not introduce a dedicated permission-history table.

---

# 39. Scope Lifecycle

The current model represents administrative scope through:

```text
admin_scope
```

A dedicated:

```
scope_history
```

table is not currently frozen.

---

# 40. Security and Person

The Person entity remains outside the Authentication table set.

Conceptually:

```text
Person
   │
   ▼
user_account
```

The exact FK relationship is subject to the final Person/Authentication
schema alignment.

---

# 41. Security and Sangha Sevi ID

Sangha Sevi ID remains a Membership identity.

It is not the authentication username by default.

The authentication account and Membership identity remain separate concepts.

---

# 42. Security and Organizational Scope

A user's organizational scope is not a replacement for Organization data.

It is an authorization boundary derived from the authoritative organization
hierarchy.

---

# 43. Security and Modules

Business modules consume effective authorization.

Conceptually:

```text
Authentication
      ↓
Authorization
      ↓
┌──────────┬───────────┬───────────┬──────────┐
│Membership│ Attendance│ Governance│  Sevak   │
└──────────┴───────────┴───────────┴──────────┘
```

No business module creates a second authentication or RBAC system.

---

# 44. Example — Sevak

The Sevak module uses:

```text
Existing ERP RBAC
+
Organizational Scope
```

rather than a separate Sevak authorization architecture.

This is explicitly established by the Sevak business rules.

---

# 45. Example — Scope

A user may conceptually have:

```text
Role:
    SAKHA_ADMIN

Permission:
    MEMBER_VIEW

Scope:
    SAKHA-001
```

The effective result is access to the permitted operation within the
authorized Sakha scope.

---

# 46. No Hard-Coded Position Authorization

The ERD does not establish:

```text
President → unrestricted access
Secretary → unrestricted access
Parichalak → unrestricted access
```

as database rules.

Authorization is represented through RBAC and scope.

---

# 47. Physical FK Boundary

The logically expected relationships are:

```text
user_role → user_account
user_role → role_master

role_permission → role_master
role_permission → permission_master

password_history → user_account
```

The exact FK names and delete behaviour are finalized in Table Design.

---

# 48. Organization FK Boundary

The exact relationship between:

```text
admin_scope
```

and:

```text
Organization
```

must be finalized after confirming the Organization table structure.

No unsupported FK is invented here.

---

# 49. Person FK Boundary

The exact relationship between:

```text
user_account
```

and:

```text
person
```

must be aligned with the final Person/Identity design.

No duplicate Person identity is introduced.

---

# 50. Tables Not Added

The current ERD does not introduce:

```text
login_history
session_history
password_reset
password_policy
account_lockout
mfa_configuration
trusted_device
security_event
role_history
permission_history
scope_history
user_permission
security_audit
```

These require explicit approved requirements.

---

# 51. Current ERD Entity Set

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

# 52. Relationship Matrix

| Source            | Target              | Relationship        | Status                 |
| ----------------- | ------------------- | ------------------- | ---------------------- |
| `user_account`    | `password_history`  | 1:N                 | Logical/source-aligned |
| `user_account`    | `user_role`         | 1:N                 | Source-supported       |
| `user_role`       | `role_master`       | N:1                 | Source-supported       |
| `role_master`     | `role_permission`   | 1:N                 | Source-supported       |
| `role_permission` | `permission_master` | N:1                 | Source-supported       |
| `user_account`    | `admin_scope`       | Scope association   | Logical                |
| `admin_scope`     | Organization        | Scope dependency    | Logical                |
| `user_account`    | Person              | Identity dependency | Logical                |

---

# 53. Security Architecture Summary

```text
                     PERSON
                       │
                       ▼
                ┌──────────────┐
                │ user_account │
                └──────┬───────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      password_history       user_role
                                 │
                                 ▼
                           role_master
                                 │
                                 ▼
                         role_permission
                                 │
                                 ▼
                       permission_master

                user_account
                       │
                       ▼
                  admin_scope
                       │
                       ▼
                 Organization
                       │
                       ▼
              Effective Access
```

---

# 54. Core Principle

The central Authentication & Security ERD principle is:

```text
Authenticate identity first.
Then evaluate centralized authorization.
Then apply organizational scope.
```

---

# 55. Design Boundary

This ERD freezes the current logical security foundation:

```
Authentication Account
Password History
Roles
Permissions
Role Assignments
User Assignments
Organizational Scope
```

It does not freeze:

```
MFA
Session History
Login History
Password Reset
Account Lockout
Role History
Scope History
Security Event Repository
```

Those require separate approved requirements.

---

# 56. Source Alignment

The PostgreSQL schema review identifies the Authentication & Security
foundation as exactly seven tables:

```
user_account
password_history
role_master
permission_master
role_permission
user_role
admin_scope
```

The project security standards identify:

```
RBAC
JWT Authentication
Password Hashing
Encrypted Sensitive Data
Audit Logging
Session Management
```

as security standards.

This ERD therefore preserves the existing seven-table foundation and does
not add unsupported authentication tables.

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
