# NSS ERP — Administration Entity Relationship Design

**Document ID:** SOL-ADMIN-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
centralized Administration/RBAC foundation.

The source identifies the following security and administration entities:

    user_account
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

These form the current source-supported RBAC foundation.

---

# 2. Core Administration Model

The central authorization model is:

    User
      ↓
    Role
      ↓
    Permission

with organizational scope applied where required:

    User
      ↓
    Administrative Scope
      ↓
    Effective Access

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
                  ┌─────────────┐    ┌─────────────┐
                  │  user_role  │    │ admin_scope │
                  └──────┬──────┘    └─────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ role_master │
                  └──────┬──────┘
                         │
                         ▼
                 ┌──────────────────┐
                 │ role_permission  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │permission_master │
                 └──────────────────┘
```

---

# 4. `user_account`

## Purpose

Represents the authenticated ERP user account.

Authentication remains responsible for verifying the user's identity.

Administration uses the account for authorization management.

---

# 5. `role_master`

## Purpose

Represents a reusable authorization role.

A role groups permissions that may be assigned to users.

Logical relationship:

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

# 6. `permission_master`

## Purpose

Represents an individual application permission/action.

Permissions are centrally defined rather than independently created by
business modules.

Logical relationship:

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

# 7. `role_permission`

## Purpose

Represents the many-to-many relationship between roles and permissions.

A role may have multiple permissions.

A permission may be assigned to multiple roles.

Therefore:

```text
role_master
     1
     │
     │
     N
role_permission
     N
     │
     │
     1
permission_master
```

---

# 8. `user_role`

## Purpose

Represents assignment of roles to users.

A user may have one or more roles where permitted by the authorization
model.

A role may be assigned to multiple users.

Therefore:

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

# 9. `admin_scope`

## Purpose

Represents organizational scope associated with administrative access.

The source identifies organizational scope levels including:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

The exact physical scope-column design is to be finalized during table
design.

---

# 10. Role + Scope Model

The logical authorization model is:

```text
                 user_account
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
         user_role          admin_scope
             │                   │
             ▼                   │
        role_master              │
             │                   │
             ▼                   │
      role_permission            │
             │                   │
             ▼                   │
     permission_master           │
             │                   │
             └─────────┬─────────┘
                       ▼
                Effective Access
```

---

# 11. Effective Authorization

Effective access is determined by the combination of:

```
User
Role
Permission
Organizational Scope
```

Not every role assignment automatically implies unrestricted global access.

---

# 12. Scope Hierarchy

The organizational hierarchy remains owned by the Organization module.

Conceptually:

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

Administration uses this hierarchy for access scope.

It does not create a duplicate organization hierarchy.

---

# 13. Organization Dependency

Logical relationship:

```text
Organization
      │
      ▼
Organizational Hierarchy
      │
      ▼
Administrative Scope
      │
      ▼
Effective Authorization
```

The exact physical FK structure between `admin_scope` and Organization
tables is not frozen by this ERD.

---

# 14. No Duplicate Organization Tables

Administration shall not create:

```
admin_kendra
admin_anchalika
admin_zilla
admin_sakha
```

The authoritative organization entities remain in the Organization module.

---

# 15. User-to-Role Relationship

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

This permits reusable role definitions.

---

# 16. Role-to-Permission Relationship

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

This provides centralized RBAC.

---

# 17. Many-to-Many Model

The complete RBAC relationship is therefore:

```text
User
 │
 └──< User Role >── Role
                       │
                       └──< Role Permission >── Permission
```

---

# 18. Scope Relationship

Scope is applied alongside role/permission.

Conceptually:

```text
User
 │
 ├── Role
 │
 └── Scope
       │
       ▼
Organizational Boundary
```

The exact physical relationship between `user_account` and `admin_scope`
requires final table-design confirmation.

---

# 19. No Permission Ownership by Business Modules

A business module does not own its own RBAC system.

For example, the Sevak module does not create:

```
sevak_role
sevak_permission
sevak_user_role
```

Instead:

```text
Sevak
  │
  ▼
Common Permission
  │
  ▼
Administration / RBAC
```

The existing Sevak rules explicitly establish this principle.

---

# 20. Example — Sevak Authorization

Conceptually:

```text
User
 │
 ├── Role
 │
 ├── Permission
 │      └── SEVAK_OPERATION
 │
 └── Scope
        └── SAKHA
```

The Sevak module consumes the resulting authorization decision.

---

# 21. Example — UPBS Authorization

```text
User
 │
 ├── Role
 │
 ├── Permission
 │      └── UPBS_REGISTRATION_MANAGE
 │
 └── Scope
        └── Appropriate Organizational Scope
```

UPBS remains the business owner.

Administration provides authorization.

---

# 22. Example — Attendance Authorization

```text
User
 │
 ├── Role
 ├── Permission
 │      └── ATTENDANCE_REVIEW
 └── Scope
        └── SAKHA / ZILLA / KENDRA
```

Attendance remains the business owner.

---

# 23. Example — Governance Authorization

```text
User
 │
 ├── Role
 ├── Permission
 │      └── GOVERNANCE_MANAGE
 └── Scope
```

Governance remains the business owner.

---

# 24. Role Does Not Equal Position

A Governance position such as:

```
President
Secretary
Parichalak
```

is not automatically identical to:

```
role_master
```

A position belongs to the Governance/business model.

A role belongs to the application authorization model.

---

# 25. Position-to-Role Mapping

Where a Governance position results in application authority, an explicit
mapping may be established.

Conceptually:

```text
Governance Position
        │
        ▼
Authorization Mapping
        │
        ▼
Application Role
```

The physical mapping is not frozen by this ERD.

---

# 26. Authentication Boundary

Authentication verifies:

```
Who is the user?
```

Administration determines:

```
What may the user do?
```

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
      ▼
Effective Access
```

---

# 27. No Duplicate Authentication

Administration does not create a separate:

```
login_user
admin_user
technical_user
```

identity system.

---

# 28. Permission Boundary

Permissions represent actions rather than business records.

For example:

```text
MEMBER_VIEW
MEMBER_EDIT
ATTENDANCE_REVIEW
GOVERNANCE_MANAGE
UPBS_REGISTRATION_MANAGE
```

These are conceptual examples.

The final permission catalogue remains pending detailed RBAC design.

---

# 29. Permission Naming

The final permission naming convention shall be consistent and centrally
controlled.

The physical naming standard will be finalized with the Administration
Table Design.

---

# 30. Role Inheritance

The current source does not establish a frozen role-inheritance hierarchy.

Therefore this ERD does not introduce:

```
parent_role_pk
```

or equivalent role inheritance.

---

# 31. Permission Groups

The current source does not establish a separate:

```
permission_group
```

entity.

No permission-group table is added to the current ERD.

---

# 32. Role History

The current source does not establish a separate:

```
role_history
```

table.

Historical role-assignment requirements will require separate design if
needed.

---

# 33. Scope History

The current source does not establish a separate:

```
scope_history
```

table.

Historical scope requirements will require separate design if needed.

---

# 34. Effective-Dated Authorization

The current ERD does not freeze a general effective-from/effective-to
authorization model.

If required, it must be introduced through detailed business rules and
table design.

---

# 35. Audit Relationship

Administrative changes may be audited.

Conceptually:

```text
Role Assignment
      │
      ├── user_role
      │
      └── Audit Event

Permission Change
      │
      ├── role_permission
      │
      └── Audit Event

Scope Change
      │
      ├── admin_scope
      │
      └── Audit Event
```

Audit remains a separate cross-cutting module.

---

# 36. No Administration Audit Table

The ERD does not introduce:

```
administration_audit
```

Audit events use the common Audit framework.

---

# 37. Organizational Scope Example

Example:

```text
User:
    U001

Role:
    SAKHA_ADMIN

Permission:
    MEMBER_VIEW

Scope:
    SAKHA-001
```

Effective result:

```text
U001
    may view members
    within the authorized Sakha scope
```

The exact implementation is finalized during table/API design.

---

# 38. Scope Does Not Change Identity

Changing a user's scope does not create a new person or user identity.

The same user account remains associated with the user.

---

# 39. Role Change Does Not Create New User

Changing a user's role does not create a new `user_account`.

The role assignment changes.

---

# 40. Permission Change Does Not Change Role Identity

Adding or removing a permission changes the role's authorization definition.

It does not create a new user identity.

---

# 41. Administrative Access Flow

```text
Login
  │
  ▼
Authenticated User
  │
  ▼
user_account
  │
  ├── user_role
  │      │
  │      ▼
  │  role_master
  │      │
  │      ▼
  │  role_permission
  │      │
  │      ▼
  │ permission_master
  │
  └── admin_scope
          │
          ▼
   Organizational Scope
          │
          ▼
   Effective Authorization
```

---

# 42. Central Authorization

The central Administration model means that a module should ask:

```
Does this user have permission X within scope Y?
```

rather than:

```
Is this user a Secretary?
```

Authorization shall be based on permission and scope, not hard-coded office
title checks.

---

# 43. No Hard-Coded Office-Bearer Authorization

The ERD does not encode:

```text
President → always allowed
Secretary → always allowed
Parichalak → always allowed
```

as universal database relationships.

Specific authority is governed through the approved authorization model.

---

# 44. Super Administrator

A high-level administrative role may exist.

However, the ERD does not create a special:

```
super_admin
```

table.

It remains a role/authorization concept.

---

# 45. Administrative Dashboard

The Administration Dashboard consumes the RBAC model.

Conceptually:

```text
user_account
      │
      ▼
Effective Authorization
      │
      ▼
Administration Dashboard
```

Only authorized administrative functions should be exposed.

---

# 46. Historical Accountability

Administrative actions must remain attributable where auditability is
required.

For example:

```text
User Role Assignment
        │
        ▼
Audit
```

Historical audit remains independent from current RBAC state.

---

# 47. Current Source-Supported Entities

```text
user_account
role_master
permission_master
role_permission
user_role
admin_scope
```

These are the source-supported RBAC foundation entities.

---

# 48. Current ERD

```text
┌──────────────────┐
│  user_account    │
└────────┬─────────┘
         │
         ├───────────────────┐
         │                   │
         ▼                   ▼
┌──────────────────┐   ┌───────────────┐
│    user_role     │   │  admin_scope  │
└────────┬─────────┘   └───────────────┘
         │
         ▼
┌──────────────────┐
│   role_master    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ role_permission  │
└────────┬─────────┘
         │
         ▼
┌────────────────────┐
│ permission_master  │
└────────────────────┘
```

---

# 49. Relationship Matrix

| Source            | Target              | Relationship          | Status                   |
| ----------------- | ------------------- | --------------------- | ------------------------ |
| `user_account`    | `user_role`         | 1:N                   | Source-supported         |
| `user_role`       | `role_master`       | N:1                   | Source-supported         |
| `role_master`     | `role_permission`   | 1:N                   | Source-supported         |
| `role_permission` | `permission_master` | N:1                   | Source-supported         |
| User              | `admin_scope`       | Scope association     | Source-supported concept |
| Organization      | `admin_scope`       | Organizational scope  | Logical                  |
| Administration    | Business Modules    | Authorization service | Cross-cutting            |
| Administration    | Audit               | Audit integration     | Cross-cutting            |

---

# 50. Physical FK Boundary

The following logical relationships are clear:

```text
user_role → user_account
user_role → role_master

role_permission → role_master
role_permission → permission_master
```

The exact physical FK columns and names will be finalized in Table Design.

The exact physical relationship between `admin_scope` and Organization
entities is also pending detailed schema confirmation.

---

# 51. Tables Not Added

The current ERD does not introduce:

```text
role_history
scope_history
permission_group
role_inheritance
permission_group_permission
admin_action
administration_audit
admin_user
admin_kendra
admin_anchalika
admin_zilla
admin_sakha
```

These require separate approved requirements.

---

# 52. Design Principle

The central ERD principle is:

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

# 53. Module Boundary

Administration owns:

```
Authorization Management
```

Organization owns:

```
Organizational Structure
```

Authentication owns:

```
Identity Verification
```

Governance owns:

```
Governance Positions and Bodies
```

Audit owns:

```
Audit History
```

Business modules own:

```
Their business operations
```

---

# 54. Source Alignment

The current project schema review identifies the centralized security/RBAC
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

with the RBAC entities used as the basis for centralized access control.

The Administration module is explicitly part of the frozen top-level module
hierarchy and the Django application structure.

The Sevak rules explicitly state that Sevak uses the existing ERP RBAC plus
organizational scope and that the detailed permission matrix is defined
centrally in Administration/RBAC.

---

# 55. Status

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
