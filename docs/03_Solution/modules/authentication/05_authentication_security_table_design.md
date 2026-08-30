# NSS ERP — Authentication & Security Table Design

**Document ID:** SOL-AUTH-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the
Authentication & Security foundation of NSS ERP.

The current source-supported foundation contains exactly seven tables:

    user_account
    password_history

    role_master
    permission_master
    role_permission
    user_role

    admin_scope

No additional authentication/security tables are frozen by this document.

---

# 2. Current Frozen Table Set

| # | Table | Responsibility |
|---:|---|---|
| 1 | `user_account` | ERP authentication account |
| 2 | `password_history` | Password-history/security record |
| 3 | `role_master` | Application role definition |
| 4 | `permission_master` | Application permission definition |
| 5 | `role_permission` | Role-to-permission relationship |
| 6 | `user_role` | User-to-role relationship |
| 7 | `admin_scope` | Organizational authorization scope |

The PostgreSQL schema review confirms these seven tables as the
Authentication & Security foundation.

---

# 3. Responsibility Split and Table Ownership

The seven tables are logically divided into two areas with **exclusive ownership**.

## Authentication & Security OWNS (DDL authority)

    user_account
    password_history

## Administration OWNS (DDL authority)

    role_master
    permission_master
    role_permission
    user_role
    admin_scope

Authentication & Security manages authentication and credential security.
Administration manages the RBAC/authorization portion.

Both modules may **reference** the other's tables via foreign keys, but
**ownership is exclusive** — only the owning module may alter the table's
DDL definition, add columns, or change constraints.

This ownership declaration is canonical. Frozen 2026-08-26.

---

# 4. Design Principle

The database shall distinguish:

    Identity
    Authentication
    Authorization
    Organizational Scope

These are related but separate concepts.

---

# 5. Primary Key Standard

The project database standard uses technical primary keys.

The established naming convention is:

    <table_name>_pk

Therefore the logical PK names are:

    user_account_pk
    password_history_pk
    role_master_pk
    permission_master_pk
    role_permission_pk
    user_role_pk
    admin_scope_pk

The exact data type and generation mechanism follow the project-wide
database standard.

---

# 6. UUID Standard

The project database architecture uses UUID-based internal primary keys.

Authentication & Security tables shall follow the same technical PK
architecture.

Business identifiers, where required, shall remain separate from internal
primary keys.

---

# 7. `user_account`

## 7.1 Purpose

`user_account` represents the ERP account used to authenticate an
authorized identity.

It is an account entity, not a Person entity.

---

## 7.2 Primary Key

Logical primary key:

    user_account_pk

---

## 7.3 Identity Relationship

The account shall be associated with the authoritative Person/identity
architecture.

Conceptually:

    Person
       ↓
    user_account
       ↓
    Authentication

The exact FK column is to be aligned with the final Person/Authentication
schema.

---

## 7.4 Account Responsibility

`user_account` is responsible for account-level authentication state.

It shall not store the complete authorization model directly.

Authorization is represented through:

    user_role
    admin_scope

---

## 7.5 No Embedded Role

The authoritative RBAC relationship shall not be represented only through
a field such as:

    role_name

inside `user_account`.

The normalized `user_role` relationship remains authoritative.

---

## 7.6 No Embedded Permission List

`user_account` shall not contain a denormalized permission list.

Effective permissions are derived through the RBAC relationships.

---

## 7.7 Account Lifecycle

The final implementation shall support controlled account lifecycle.

Possible states such as:

    ACTIVE
    INACTIVE
    LOCKED

are design candidates only.

The final status catalogue remains pending.

---

# 8. `password_history`

## 8.1 Purpose

`password_history` represents historical password-security information
associated with a user account.

---

## 8.2 Primary Key

Logical primary key:

    password_history_pk

---

## 8.3 User Relationship

Logical relationship:

    user_account
          1
          │
          N
    password_history

A user account may therefore have multiple password-history records.

---

## 8.4 Foreign Key

Logical relationship:

    password_history.user_account_pk
              ↓
    user_account.user_account_pk

The exact physical FK name is finalized in PostgreSQL DDL.

---

## 8.5 Password History Is Not Current Credential

Password history is historical security information.

It shall not be treated as the current authentication credential.

---

## 8.6 Password Storage

Passwords shall never be stored as plaintext.

The project security baseline identifies Argon2 password hashing.

The final Django implementation shall use the approved secure password
hashing mechanism.

---

## 8.7 Password Reuse

`password_history` provides the database foundation required to enforce a
password-reuse policy.

The exact number of previous passwords that cannot be reused is not frozen
by the current source.

---

# 9. `role_master`

## 9.1 Purpose

`role_master` contains reusable application authorization roles.

---

## 9.2 Primary Key

Logical primary key:

    role_master_pk

---

## 9.3 Role Identity

A role shall have a stable technical identity.

The final design may include concepts such as:

    Role Code
    Role Name
    Description
    Active State

However, the current source does not provide an authoritative complete
column list.

Therefore these are logical design concepts, not frozen columns.

---

## 9.4 Role Uniqueness

Role identifiers/codes intended to be unique shall have an appropriate
unique constraint.

The exact unique key is pending final schema approval.

---

## 9.5 Role Lifecycle

Inactive roles must not automatically destroy historical authorization
evidence.

---

# 10. `permission_master`

## 10.1 Purpose

`permission_master` contains the centrally defined application permissions.

---

## 10.2 Primary Key

Logical primary key:

    permission_master_pk

---

## 10.3 Permission Identity

Each permission shall have a stable technical identity.

The final design may use:

    Permission Code
    Permission Name
    Description
    Module/Domain
    Active State

but the complete column list is not frozen by the current source.

---

## 10.4 Permission Catalogue

The complete permission catalogue is not currently frozen.

No complete permission seed list is declared by this document.

---

# 11. `role_permission`

## 11.1 Purpose

`role_permission` implements the many-to-many relationship between roles and
permissions.

Logical model:

    role_master
          │
          └──< role_permission >── permission_master

---

## 11.2 Primary Key

Logical primary key:

    role_permission_pk

---

## 11.3 Foreign Key — Role

Logical relationship:

    role_permission.role_master_pk
             ↓
    role_master.role_master_pk

---

## 11.4 Foreign Key — Permission

Logical relationship:

    role_permission.permission_master_pk
             ↓
    permission_master.permission_master_pk

---

## 11.5 Duplicate Mapping

The same permission should not be assigned more than once to the same role.

The final schema should enforce uniqueness over:

    role_master_pk
    permission_master_pk

---

## 11.6 Permission Deactivation

Deactivating a permission must not silently rewrite historical authorization
information.

The final lifecycle/delete behaviour is subject to the approved RBAC
implementation.

---

# 12. `user_role`

## 12.1 Purpose

`user_role` represents assignment of application roles to user accounts.

Logical model:

    user_account
          │
          └──< user_role >── role_master

---

## 12.2 Primary Key

Logical primary key:

    user_role_pk

---

## 12.3 Foreign Key — User

Logical relationship:

    user_role.user_account_pk
             ↓
    user_account.user_account_pk

---

## 12.4 Foreign Key — Role

Logical relationship:

    user_role.role_master_pk
             ↓
    role_master.role_master_pk

---

## 12.5 Duplicate Role Assignment

The same role should not be assigned repeatedly to the same active user.

The final schema should enforce appropriate uniqueness.

---

## 12.6 Multiple Roles

The relationship supports assignment of multiple roles to a user where the
approved authorization model permits it.

---

# 13. `admin_scope`

## 13.1 Purpose

`admin_scope` represents organizational scope for authorization.

Known scope levels are:

    KENDRA
    ANCHALIKA
    ZILLA
    SAKHA

---

## 13.2 Primary Key

Logical primary key:

    admin_scope_pk

---

## 13.3 Scope Level

Scope level shall be controlled.

The final implementation shall not allow arbitrary unsupported scope
values.

---

## 13.4 Organization Dependency

`admin_scope` shall refer to the authoritative Organization structure.

Administration shall not create duplicate organization entities.

---

## 13.5 Scope Target

A scope record logically needs to identify the organizational unit to which
the authorization applies.

The exact FK target depends on the finalized Organization table design.

Therefore the physical FK is not frozen here.

---

# 14. User-to-Scope Relationship

The logical authorization model is:

    user_account
          │
          └──< admin_scope

The current source identifies `admin_scope` but does not provide its complete
column-level definition.

Therefore the exact user/scope FK representation remains pending final
schema design.

---

# 15. Scope and Organization

The logical relationship is:

    Organization
          ↓
    admin_scope
          ↓
    Effective Authorization

`admin_scope` is an authorization representation of organizational scope,
not a replacement for Organization.

---

# 16. Organization Hierarchy

The authoritative Organization module owns:

    Kendra
    Anchalika
    Zilla
    Sakha

Administration and Authentication use that hierarchy for authorization.

---

# 17. No Duplicate Organization Tables

The Authentication & Security schema shall not create:

    admin_kendra
    admin_anchalika
    admin_zilla
    admin_sakha

---

# 18. Effective Authorization

The database relationships support:

    User
      ↓
    Role
      ↓
    Permission

plus:

    Organizational Scope

Therefore:

    User
    +
    Role
    +
    Permission
    +
    Scope
    =
    Effective Authorization

The final authorization decision is made by the application/security
layer.

---

# 19. Authorization Derivation

The normalized permission path is:

    user_account
          ↓
    user_role
          ↓
    role_master
          ↓
    role_permission
          ↓
    permission_master

Scope is evaluated alongside this path:

    admin_scope
          ↓
    Organization

---

# 20. No `user_permission`

The current foundation does not contain:

    user_permission

Direct user-to-permission mapping shall not be introduced unless separately
approved.

---

# 21. No Permission List

The following denormalized structures are not part of the design:

    user_account.permission_list
    role_master.permission_list

Permissions remain normalized through `role_permission`.

---

# 22. Person Relationship

The final `user_account` design shall align with the authoritative Person
schema.

The Authentication module shall not create:

    authentication_person

or another duplicate identity entity.

---

# 23. Membership Relationship

Authentication shall not use Membership as a substitute for the user
account.

Membership remains responsible for:

    Membership Identity
    Sangha Sevi ID
    Membership Lifecycle

---

# 24. Sangha Sevi ID

The earlier project SQL planning identifies:

    sangha_sevi_id

as the login ID concept.

The final `user_account` implementation must remain aligned with the
approved Person/Membership identity design.

It shall not create a second unrelated login identity without an approved
change.

---

# 25. Governance Position Boundary

Governance positions such as:

    President
    Secretary
    Parichalak

are not automatically stored as `role_master` rows.

Governance owns positions.

Administration owns application roles.

Any mapping requires explicit approval.

---

# 26. Security Audit

No dedicated:

    security_audit

table is introduced.

Security-related auditable actions use the common Audit framework.

---

# 27. Login History

No dedicated:

    login_history

table is currently frozen.

If required later, it requires explicit approval.

---

# 28. Session History

The project security standard requires session management, but the current
database foundation does not include:

    session_history

Session implementation shall therefore not be assumed to require a new
table.

---

# 29. MFA

No:

    mfa_configuration

table is frozen.

MFA remains a pending security capability unless separately approved.

---

# 30. Password Reset

No:

    password_reset
    password_reset_token

tables are currently frozen.

---

# 31. Account Lockout

No separate:

    account_lockout

table is currently frozen.

---

# 32. Role History

No separate:

    role_history

table is currently frozen.

Historical authorization evidence shall use the approved audit/history
architecture.

---

# 33. Scope History

No separate:

    scope_history

table is currently frozen.

Any effective-dated scope history requirement requires separate approval.

---

# 34. Standard Audit Metadata

Where applicable, tables shall follow the project database audit standard.

The project standard identifies:

    created_at
    created_by_sangha_sevi_pk
    updated_at
    updated_by_sangha_sevi_pk
    deleted_at
    deleted_by_sangha_sevi_pk
    is_active

as standard audit/lifecycle fields for applicable records.

The exact applicability to each security table shall be finalized in SQL.

---

# 35. Soft Delete

Applicable security records shall follow the project's history-preservation
principle.

Physical deletion shall not be used casually where it would destroy
historical accountability.

---

# 36. Referential Integrity

All foreign keys shall reference authoritative technical primary keys.

Foreign keys shall not reference:

    Display Names
    Labels
    Business Text
    UI Values

unless explicitly designed as an approved business-key relationship.

---

# 37. Delete Behaviour

The final SQL must explicitly define `ON DELETE` behaviour.

Cascading deletion shall not accidentally destroy historical security
information.

---

# 38. Unique Constraints

The final design should consider uniqueness for:

    Role Code
    Permission Code
    User + Role
    Role + Permission

Exact constraints depend on the final lifecycle model.

---

# 39. NOT NULL Constraints

Mandatory fields shall be declared `NOT NULL`.

The current source does not provide enough column-level detail to freeze
every NOT NULL rule.

---

# 40. CHECK Constraints

Controlled values such as:

    Scope Level

shall be constrained through the approved project master-data/controlled
value mechanism.

---

# 41. Indexing

The final implementation should support efficient lookups for:

    User → Roles
    Role → Permissions
    Permission → Roles
    User → Scope
    Scope → Users

Relevant foreign-key columns should therefore be indexed where appropriate.

---

# 42. Authorization Query Path

The expected logical access path is:

    user_account
          ↓
    user_role
          ↓
    role_master
          ↓
    role_permission
          ↓
    permission_master

combined with:

    admin_scope
          ↓
    Organization

---

# 43. API Dependency

The table design supports API-level authorization.

The API shall evaluate:

    Authentication
    Permission
    Organizational Scope

Database integrity alone is not the authorization boundary.

---

# 44. UI Dependency

The UI may hide unavailable functions based on authorization.

However, UI visibility is not a security control.

Backend/API authorization remains mandatory.

---

# 45. RLS Boundary

The project security architecture identifies Row-Level Security (RLS) as a
security principle.

The exact tables requiring RLS and the policy definitions are not frozen by
this table-design document.

---

# 46. Encryption Boundary

The project security architecture identifies encryption for sensitive data,
including Aadhaar protection.

The exact encrypted columns and cryptographic implementation are outside
this table-design baseline.

---

# 47. Password Hashing Boundary

The project security architecture identifies Argon2 password hashing.

The exact Django password configuration belongs to the implementation/API
security design.

---

# 48. Current Physical Schema Boundary

The following table identities are frozen:

    user_account
    password_history
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

The following are not frozen:

    Exact complete column lists
    Exact password policy fields
    Session tables
    Login-history tables
    MFA tables
    Password-reset tables
    Lockout tables
    Role-history tables
    Scope-history tables

---

# 49. Tables Explicitly Not Added

```text
login_history
session_history
password_reset
password_reset_token
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

No additional table should be introduced without an approved requirement.

---

# 50. Final DDL Prerequisites

Before generating PostgreSQL DDL, the following must be finalized:

```
Complete user_account columns
Person/user relationship
Complete password_history columns
Password-history retention policy
Complete role_master columns
Complete permission_master columns
Permission catalogue
Complete role_permission columns
Complete user_role columns
Complete admin_scope columns
User/scope relationship
Organization/scope relationship
Exact PK definitions
Exact FK definitions
Exact unique constraints
Exact CHECK constraints
Exact indexes
Exact audit fields
Exact delete behaviour
RLS policy requirements
```

---

# 51. Database-First Principle

Authentication & Security follows:

```
Business Rules
      ↓
ERD
      ↓
Table Design
      ↓
PostgreSQL DDL
      ↓
ORM
      ↓
API
      ↓
UI
      ↓
Testing
      ↓
Release
```

No DDL shall be generated from unsupported assumptions.

---

# 52. Source Alignment

The PostgreSQL schema review identifies the Authentication & Security
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

The earlier SQL implementation planning confirms the Authentication phase
as:

```
user_account.sql
password_history.sql
rbac.sql
admin_scope.sql
```

and identifies the scope values:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

The project security architecture additionally establishes security
principles including RBAC, JWT Authentication, password hashing, encrypted
sensitive data, audit logging, session management, and RLS. These principles
do not by themselves authorize additional database tables.

---

# 53. Status

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
