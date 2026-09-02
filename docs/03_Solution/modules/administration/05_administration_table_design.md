# NSS ERP — Administration Table Design

**Document ID:** SOL-ADMIN-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the table-design baseline for the centralized
Administration/RBAC capability.

The source-supported authorization foundation consists of:

    user_account
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

The Authentication & Security foundation additionally contains:

    password_history

`password_history` remains under Authentication & Security and is not
duplicated in Administration.

---

# 2. Current Source-Supported Tables

| # | Table | Responsibility |
|---:|---|---|
| 1 | `user_account` | Authenticated ERP account |
| 2 | `role_master` | Role definitions |
| 3 | `permission_master` | Permission definitions |
| 4 | `role_permission` | Role-to-permission mapping |
| 5 | `user_role` | User-to-role mapping |
| 6 | `admin_scope` | Organizational authorization scope |

Authentication dependency:

| Table | Owner |
|---|---|
| `password_history` | Authentication & Security |

The source identifies all seven tables in the centralized Security foundation.

## Table Ownership Declaration (Frozen)

**Administration OWNS (DDL authority):**

    role_master
    permission_master
    role_permission
    user_role
    admin_scope
    correspondence
    correspondence_document
    correspondence_finance_reference

**Authentication & Security OWNS (DDL authority):**

    user_account
    password_history

Both modules may **reference** the other's tables via foreign keys, but
**ownership is exclusive** — only the owning module may alter the table's
DDL definition, add columns, or change constraints.

---

# 3. Database Naming Standard

The project standard uses:

    <table_name>_pk

for technical primary keys.

Therefore:

    user_account_pk
    role_master_pk
    permission_master_pk
    role_permission_pk
    user_role_pk
    admin_scope_pk

where a surrogate primary key is used.

---

# 4. UUID Primary Keys

The project database architecture uses UUID-based primary keys.

The final implementation shall use the approved UUID mechanism consistently
across Administration tables.

---

# 5. Foreign Key Standard

Foreign keys shall reference the target table's technical primary key.

Example:

    user_role.user_account_pk
        →
    user_account.user_account_pk

and not a business/display identifier.

This follows the established project database standard.

---

# 6. Standard Audit Metadata

Where applicable, transactional/administrative tables shall follow the
project audit metadata convention:

    created_at
    created_by_sangha_sevi_pk

    updated_at
    updated_by_sangha_sevi_pk

    deleted_at
    deleted_by_sangha_sevi_pk

    is_active

The exact applicability to each RBAC master/mapping table shall be confirmed
during final SQL design.

---

# 7. `user_account`

## 7.1 Purpose

`user_account` represents the ERP authentication account associated with a
system user.

Authentication remains responsible for verifying identity.

Administration consumes the account for authorization.

---

## 7.2 Primary Key

```text
user_account_pk
```

---

## 7.3 Identity Relationship

The account must be associated with the authoritative person/member identity
architecture.

The Administration module shall not create a duplicate Person identity.

---

## 7.4 Logical Responsibilities

`user_account` is responsible for account-level state such as:

```
Account Identity
Authentication State
Account Activation
```

The exact authentication fields are owned by the Authentication & Security
design.

---

## 7.5 Authorization Boundary

Roles and scopes are not stored as duplicated fields such as:

```
role_name
permission_list
```

inside `user_account`.

They are represented through:

```
user_role
admin_scope
```

---

# 8. `role_master`

## 8.1 Purpose

`role_master` contains reusable application authorization roles.

---

## 8.2 Primary Key

```text
role_master_pk
```

---

## 8.3 Logical Attributes

A role may require concepts such as:

```
Role Code
Role Name
Description
Active Status
```

The exact physical column names are subject to the project naming standard
and final schema review.

---

## 8.4 Role Identity

A role must have a stable technical identity.

Display labels shall not be used as relational identifiers.

---

## 8.5 Role Uniqueness

Role codes/names that are intended to be unique shall have appropriate
unique constraints.

The exact unique key requires final approval.

---

## 8.6 Role Lifecycle

Roles may become inactive without destroying historical references.

Historical role assignments must remain interpretable.

---

# 9. `permission_master`

## 9.1 Purpose

`permission_master` contains centrally defined application permissions.

---

## 9.2 Primary Key

```text
permission_master_pk
```

---

## 9.3 Logical Attributes

A permission may require:

```
Permission Code
Permission Name
Description
Module/Domain
Active Status
```

The exact physical columns are not independently frozen by the current
source.

---

## 9.4 Permission Identity

A permission shall have a stable identifier/code.

Application code should not depend solely on a display label.

---

## 9.5 Permission Catalogue

The complete permission catalogue is not yet frozen.

Therefore this document does not create a final list of permission rows.

---

# 10. `role_permission`

## 10.1 Purpose

`role_permission` represents the relationship between roles and permissions.

Logical model:

```text
role_master
     │
     └──< role_permission >── permission_master
```

---

## 10.2 Primary Key

```text
role_permission_pk
```

---

## 10.3 Foreign Keys

Logical foreign keys:

```text
role_permission.role_master_pk
        →
role_master.role_master_pk
```

and:

```text
role_permission.permission_master_pk
        →
permission_master.permission_master_pk
```

---

## 10.4 Duplicate Mapping Prevention

The same role should not receive the same permission more than once.

Therefore the final schema should enforce uniqueness across:

```text
role_master_pk
+
permission_master_pk
```

---

## 10.5 Role Deactivation

Deactivating a role shall not silently destroy historical authorization
evidence.

The final deletion behavior must preserve referential integrity.

---

# 11. `user_role`

## 11.1 Purpose

`user_role` represents assignment of roles to user accounts.

Logical model:

```text
user_account
      │
      └──< user_role >── role_master
```

---

## 11.2 Primary Key

```text
user_role_pk
```

---

## 11.3 Foreign Keys

Logical foreign keys:

```text
user_role.user_account_pk
        →
user_account.user_account_pk
```

and:

```text
user_role.role_master_pk
        →
role_master.role_master_pk
```

---

## 11.4 Duplicate Assignment Prevention

The same active role should not be assigned repeatedly to the same user.

The final schema should enforce appropriate uniqueness.

---

## 11.5 Role Assignment History

The current source does not freeze a separate:

```
role_history
```

table.

If effective-dated assignment history is required, it must be separately
approved.

---

# 12. `admin_scope`

## 12.1 Purpose

`admin_scope` represents organizational authorization scope.

Known scope levels include:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

---

## 12.2 Primary Key

```text
admin_scope_pk
```

---

## 12.3 Organizational Dependency

`admin_scope` must use the authoritative Organization hierarchy.

Administration shall not duplicate organization entities.

---

## 12.4 Logical Scope Information

A scope record may need to identify:

```
Scope Level
Organization Unit
Associated User
Active State
```

The exact physical representation requires final schema approval.

---

## 12.5 Scope Level

The scope level must be controlled.

Conceptually:

```text
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

These values shall not be silently expanded through application code.

---

## 12.6 Scope Target

The scope must identify the relevant organizational unit where the
authorization is organizationally constrained.

The exact FK target depends on the finalized Organization schema.

---

# 13. User-to-Scope Relationship

The logical authorization model is:

```text
user_account
      │
      ├── user_role
      │
      └── admin_scope
```

The source identifies `admin_scope` as part of the security foundation, but
does not provide the complete physical FK definition.

Therefore the exact user-to-scope FK remains subject to final schema
confirmation.

---

# 14. Organization Relationship

Conceptually:

```text
Organization
     │
     ▼
admin_scope
     │
     ▼
Effective Authorization
```

`admin_scope` shall not become an alternate organization table.

---

# 15. Role + Scope

The final authorization decision is conceptually:

```text
User
 +
Role
 +
Permission
 +
Organizational Scope
 =
Effective Access
```

The database stores the authorization components.

The application authorization layer evaluates the effective decision.

---

# 16. No Permission List in User Table

The schema shall not store a denormalized permission list inside
`user_account`.

Permissions are derived through:

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

# 17. No Role Name in User Table

The schema shall not use a simple:

```
user_account.role_name
```

field as the authoritative RBAC relationship.

The `user_role` mapping remains authoritative.

---

# 18. No Scope Name in User Table

The schema shall not use a simple:

```
user_account.scope_name
```

field as the authoritative scope relationship.

`admin_scope` remains the dedicated scope model.

---

# 19. Role-to-Permission Normalization

The schema shall preserve normalized many-to-many relationships.

```text
Role
  │
  └──< role_permission >── Permission
```

This avoids embedding permission lists inside role records.

---

# 20. User-to-Role Normalization

The schema shall preserve normalized many-to-many relationships.

```text
User
  │
  └──< user_role >── Role
```

---

# 21. Permission Module Ownership

A permission may identify the business module to which it applies.

However, business ownership remains with the originating module.

Example:

```text
Permission:
    SEVAK_EVENT_MANAGE

Business Owner:
    Sevak

Authorization Owner:
    Administration/RBAC
```

---

# 22. No Module-Specific Permission Tables

The Administration schema shall not introduce:

```
sevak_permission
attendance_permission
upbs_permission
membership_permission
```

or equivalent duplicate permission structures.

---

# 23. Governance Position Boundary

A Governance position is not a role-master record by default.

The Governance module owns:

```
position_master
position_assignment
```

Administration owns:

```
role_master
user_role
role_permission
```

Any mapping between them requires explicit design.

---

# 24. Membership Boundary

Membership status is not stored as an Administration role.

For example:

```
Regular Member
Probationary Member
Associate Member
```

remain Membership-domain concepts.

They do not automatically become `role_master` rows.

---

# 25. Authentication Boundary

`password_history` belongs to Authentication & Security.

Administration shall not duplicate:

```
password_history
password_hash
authentication_session
```

unless separately required by the Authentication design.

---

# 26. Password History

The source identifies:

```
password_history
```

as part of Authentication & Security.

It is therefore an external dependency of Administration rather than an
Administration table.

---

# 27. Audit Integration

Administrative table changes may produce centralized Audit events.

Examples:

```
Role Created
Role Deactivated
Permission Created
Role-Permission Assignment
User-Role Assignment
Scope Assignment
Scope Change
```

No:

```
administration_audit
```

table is introduced.

---

# 28. Historical Preservation

Current RBAC state and historical audit state are separate.

Changing:

```
Role
Permission
User Assignment
Scope
```

must not rewrite historical Audit records.

---

# 29. Soft Delete

Where applicable, administrative records shall use the project's standard
soft-delete mechanism rather than physical deletion.

Standard fields include:

```
is_active
deleted_at
deleted_by_sangha_sevi_pk
```

where applicable.

---

# 30. Delete Behavior

Foreign-key deletion behavior must prevent accidental destruction of
historical authorization relationships.

The final SQL must explicitly define appropriate `ON DELETE` behaviour.

---

# 31. Role-Permission Delete

Deleting a role must not leave orphaned `role_permission` rows.

Deleting/deactivating a role must not destroy historical audit information.

---

# 32. User-Role Delete

Deleting/deactivating a user must not cause uncontrolled destruction of
historical audit records.

The final FK/delete policy shall preserve referential integrity.

---

# 33. Scope Delete

Organizational scope records must not be deleted in a manner that invalidates
historical authorization evidence.

Organization lifecycle rules must be respected.

---

# 34. Unique Constraints

The final design should enforce uniqueness for relationships that cannot
legitimately be duplicated.

At minimum, the logical model requires consideration of:

```text
(role_master_pk, permission_master_pk)

(user_account_pk, role_master_pk)
```

Exact implementation depends on active/inactive/history requirements.

---

# 35. NOT NULL Rules

Required fields shall be `NOT NULL`.

The exact field-level NULLability will be finalized after the complete
column catalogue is approved.

---

# 36. CHECK Constraints

Controlled values such as scope level should be constrained through the
approved master-data/controlled-value mechanism.

The final implementation must not permit invalid organizational scope
values.

---

# 37. Indexing

The final schema should provide efficient lookup for:

```
User → Roles
Role → Permissions
Permission → Roles
User → Scope
Scope → Users
```

Recommended relational access paths include indexes on the relevant FK
columns.

---

# 38. Scope Indexing

Because scope-sensitive authorization is expected to be common, the final
implementation should support efficient filtering by:

```
Scope Level
Organization Unit
User
```

---

# 39. Permission Indexing

The final implementation should support efficient lookup of permissions
associated with a role.

---

# 40. Role Assignment Indexing

The final implementation should support efficient lookup of roles assigned
to a user.

---

# 41. Authorization Query Model

The logical query path is:

```text
User
 ↓
user_role
 ↓
role_master
 ↓
role_permission
 ↓
permission_master

+
admin_scope
 ↓
Organization Scope
```

This forms the basis for effective authorization.

---

# 42. No Authorization in UI Only

The table design supports server-side authorization.

UI visibility is not considered a database security boundary.

---

# 43. API Dependency

API endpoints that modify Administration data shall enforce:

```
Authentication
Permission
Scope
```

The database schema supports integrity; application/API logic enforces
authorization.

---

# 44. Current Source-Supported Schema

```text
user_account
role_master
permission_master
role_permission
user_role
admin_scope
```

Authentication dependency:

```text
password_history
```

---

# 45. Tables Not Added

The current Administration table design does not introduce:

```text
role_history
scope_history
permission_group
role_inheritance
user_permission
admin_action
admin_approval
administration_audit
admin_user
admin_kendra
admin_anchalika
admin_zilla
admin_sakha
```

These require separate approved requirements.

---

# 46. Physical Schema Boundary

Before generating PostgreSQL DDL, the following must be finalized:

```
Exact columns
Exact data types
Exact PK definitions
Exact FK definitions
Exact organization-scope FK
Exact unique constraints
Exact NULL/NOT NULL rules
Exact CHECK constraints
Exact indexes
Exact audit metadata
Exact delete behaviour
Exact role lifecycle
Exact scope lifecycle
Exact permission catalogue
```

---

# 47. Database-First Principle

The Administration implementation shall follow:

```text
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

No SQL shall be generated from undocumented assumptions.

---

# 48. Source Alignment

The authoritative schema review identifies the centralized security
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

for a total of seven tables in the centralized Security foundation
(five Administration-owned, two Authentication-owned).

The Correspondence Register capability adds three further Administration-owned
tables (defined in SOL-ADMIN-009):

    correspondence
    correspondence_document
    correspondence_finance_reference

bringing the Administration-owned total to eight tables.

The project database standards establish the technical PK naming convention,
FK-to-PK convention, and standard audit metadata fields.

The Administration/RBAC business rules establish centralized RBAC and
organizational scope, with individual modules consuming rather than
duplicating the authorization framework.

---

# 49. Status

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
