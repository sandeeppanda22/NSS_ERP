# NSS ERP — Administration Table Design

**Document ID:** SOL-ADMIN-004
**Version:** 1.3.0
**Status:** DRAFT — SOURCE ALIGNED
**Amendment:** §8.7–8.10 — Frozen Role Catalogue, Role ≠ Position, Permission Matrix Status;
§8.11 (v1.2.0) — Parallel Administrative Role Model: the six organizational/system admin roles
are parallel, not inherited; per-role eligibility criteria (incl. Parichay Patra eligibility for
`NSS_ERP_ADMIN`, independent of Governing Body membership); multi-role-assignment example;
§8.7/§8.8/§8.11 (v1.3.0) — added a 9th frozen role, `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`,
scoped to the single Kendra Mahila Sangha organization, per an explicit governance decision
(2026-09-25) — see Organization business rules §28 (ORG-BR-087–095) for the underlying
type-to-type parent hierarchy this role's scope depends on
**Module:** Administration
**Parent System:** Nilachala Saraswata Sangha ERP


> **Amendment (2026-10-30, owner-directed, GDR-005/GDR-006):** a 10th frozen role, `NSS_ERP_ADVISORY_BOARD_ADMIN` (scope `ADVISORY_BOARD`), is part of the catalogue; `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` reaches every `MAHILA_SANGHA` organization (not only the Kendra-parented one) with Kendra's 18 operational permissions. §8.8's "never automatic" assignment statement is qualified by the §63 composite auto-grant (live governing-body seats grant the corresponding admin scope without a `user_role` row). Final permission lists: GDR-005 §2.6 (8 permissions) and GDR-006 §2.3 (18 permissions).

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

## 8.7 Frozen Role Catalogue

The following nine RBAC roles are frozen:

| Role Code | Role Class | Scope | Intended Responsibility |
|-----------|-----------|-------|------------------------|
| `NSS_ERP_ADMIN` | System administration | NSS-wide | System-level administration and management of ERP authorization/configuration |
| `NSS_ERP_KENDRA_ADMIN` | Organizational administration | Kendra | Administrative operations within Kendra scope |
| `NSS_ERP_ANCHALIKA_ADMIN` | Organizational administration | Anchalika | Administrative operations within assigned Anchalika scope |
| `NSS_ERP_ZILLA_ADMIN` | Organizational administration | Zilla | Administrative operations within assigned Zilla scope |
| `NSS_ERP_SAKHA_ADMIN` | Organizational administration | Sakha | Administrative operations within assigned Sakha scope |
| `NSS_ERP_PATHA_CHAKRA_ADMIN` | Organizational administration | Patha Chakra | Administrative operations within assigned Patha Chakra scope |
| `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` | Organizational administration | Kendra Mahila Sangha | Administrative operations within the Kendra Mahila Sangha scope |
| `NSS_ERP_AUDITOR` | Oversight / read | NSS-wide | Audit and review access |
| `NSS_ERP_REPORT_VIEWER` | Reporting / read | NSS-wide | Reporting and read-oriented access |

All seven organizational/system administrative roles (`NSS_ERP_ADMIN`,
`NSS_ERP_KENDRA_ADMIN`, `NSS_ERP_ANCHALIKA_ADMIN`, `NSS_ERP_ZILLA_ADMIN`,
`NSS_ERP_SAKHA_ADMIN`, `NSS_ERP_PATHA_CHAKRA_ADMIN`,
`NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`) share the same
administrative permission set initially. The only distinction between
them is **scope**, not capability: `NSS_ERP_ADMIN` is system-wide,
each other administrative role is scoped to its named organizational
unit. Kendra is a singleton — there is, and will only ever be, one
Kendra — so `NSS_ERP_ADMIN` and `NSS_ERP_KENDRA_ADMIN` cover identical
effective data today. The two roles are kept separate not for future
data-scope growth but because they represent two distinct **assignment
authorities**: `NSS_ERP_ADMIN` is granted on system-wide authorization
to any eligible member (Parichay Patra basis), while
`NSS_ERP_KENDRA_ADMIN` is granted through Kendra's own Governing Body
administration path — see §8.11 for the full parallel-role model and
eligibility rules. `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` is likewise a
singleton-scoped role: the Kendra Mahila Sangha is a single
organization (see `docs/03_Solution/modules/organization/
04_organization_business_rules.md` §28, ORG-BR-091) — the organization
`MAHILA_SANGHA` row whose parent is `KENDRA` — not a per-Sakha role;
local per-Sakha Mahila Sanghas fall under their Sakha's own
`NSS_ERP_SAKHA_ADMIN` scope, not a distinct role.

Role assignment is independent of governance position. A Kendra Governing
Body member does not automatically receive `NSS_ERP_KENDRA_ADMIN`; an
authorized individual who is not a Governing Body member may receive it
if legitimately authorized to administer that organizational unit.

These roles are seeded in `role_master` during Phase 0 Bootstrap
(`database/seed/00_bootstrap/02_role_master.sql`).

---

## 8.8 Role ≠ Governance Position

RBAC roles represent **technical authorization** in the ERP.
Governance positions represent **organizational/governance
responsibility** as defined by the NSS Bye-Law.

```text
RBAC Role                    Governance Position
─────────                    ───────────────────
NSS_ERP_ADMIN                    President
NSS_ERP_KENDRA_ADMIN             Vice President
NSS_ERP_ANCHALIKA_ADMIN          Secretary
NSS_ERP_ZILLA_ADMIN              Assistant Secretary
NSS_ERP_SAKHA_ADMIN              Treasurer
NSS_ERP_AUDITOR                  Governing Body Member
NSS_ERP_REPORT_VIEWER
NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN
```

These are **independent concepts**. A President does not automatically
receive the `NSS_ERP_ADMIN` RBAC role. A `NSS_ERP_SAKHA_ADMIN` does not
automatically hold a governance position. Any mapping between them
requires explicit design and is not frozen.

Governance positions are owned by the Governance module
(`position_master`, `body_member_assignment`), not by Administration.

---

## 8.9 Permission Matrix Status

The role catalogue is frozen at the **role level**. The complete
permission catalogue and role-to-permission matrix remain pending the
Authentication/Administration physical design pass.

No `role_permission` seed data shall be created until the permission
catalogue is formally frozen.

---

## 8.10 SELF_SERVICE_MEMBER Exclusion

`SELF_SERVICE_MEMBER` was identified as a possible role during design
exploration but was **not frozen**. It is excluded from the role
catalogue and shall not be seeded into `role_master`.

If a member self-service role is required in the future, it must be
separately proposed, evaluated, and frozen before inclusion.

---

## 8.11 Parallel Administrative Role Model (Not Inherited)

The six organizational/system administrative roles form a **parallel**
structure, not a hierarchy or inheritance chain. Holding a
wider-scoped role (e.g. `NSS_ERP_ADMIN`) is never a prerequisite for,
and never automatically grants, a narrower-scoped role (e.g.
`NSS_ERP_SAKHA_ADMIN`) or vice versa. Each is a separate row in
`role_master`, assigned independently via `user_role`, with its scope
recorded independently via `admin_scope`.

```text
                  ADMINISTRATIVE ACCESS
                          │
             ┌────────────┴────────────┐
             │                         │
     NSS_ERP_ADMIN              Organizational Admin
     System-wide                       │
                                       │
                 ┌─────────────┬───────┼──────────────┬──────────────────┐
                 │             │       │              │                  │
              KENDRA       ANCHALIKA  ZILLA         SAKHA      KENDRA MAHILA SANGHA
                 │             │       │              │
                 └─────────────┴───────┴──────────────┘
                              │
                         PATHA CHAKRA
```

### Eligibility per role

| Role | Who may receive it |
|---|---|
| `NSS_ERP_ADMIN` | Any NSS member holding a valid Parichay Patra, when system-wide administration is authorized. Governing Body membership is **not** a prerequisite. |
| `NSS_ERP_KENDRA_ADMIN` | Kendra Governing Body members, or another individual authorized to administer Kendra. |
| `NSS_ERP_ANCHALIKA_ADMIN` | Anchalika Governing Body members, or another authorized individual. |
| `NSS_ERP_ZILLA_ADMIN` | Zilla Governing Body members, or another authorized individual. |
| `NSS_ERP_SAKHA_ADMIN` | Sakha Governing Body members, or another authorized individual. |
| `NSS_ERP_PATHA_CHAKRA_ADMIN` | Authorized Governing Body/organizational individual for that Patha Chakra. |
| `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` | Kendra Mahila Sangha Governing Body members, or another individual authorized to administer the Kendra Mahila Sangha. Scoped to the single Kendra Mahila Sangha organization only — not to local, per-Sakha Mahila Sanghas (see Organization business rules §28, ORG-BR-091). |
| `NSS_ERP_AUDITOR` | Authorized auditor. |
| `NSS_ERP_REPORT_VIEWER` | Authorized report user. |

Governing Body membership makes a person a natural candidate for the
role scoped to their own organizational unit, but per §8.8 it is never
automatic — assignment is always an explicit `user_role` row.

### Assignment chain examples

A Kendra Governing Body member:

```text
Sangha Sevi → user_account → user_role → NSS_ERP_KENDRA_ADMIN → admin_scope → Kendra
```

A Sakha Governing Body member:

```text
Sangha Sevi → user_account → user_role → NSS_ERP_SAKHA_ADMIN → admin_scope → Specific Sakha
```

An eligible NSS member authorized for full system administration:

```text
Sangha Sevi → user_account → user_role → NSS_ERP_ADMIN → System-wide
```

### Multiple simultaneous assignments

A single Sangha Sevi may hold more than one administrative role at
once, each with its own scope — this is the existing `user_role` (1:N
from `user_account`) + `admin_scope` (attached per role assignment,
not per person) architecture already frozen in §11–§12, applied here
to the organizational-admin role set specifically:

```text
SS000123
   ├── NSS_ERP_KENDRA_ADMIN → Kendra
   ├── NSS_ERP_SAKHA_ADMIN  → Sakha A
   └── NSS_ERP_AUDITOR      → System
```

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
1.2.0
```

---

# End of Document
