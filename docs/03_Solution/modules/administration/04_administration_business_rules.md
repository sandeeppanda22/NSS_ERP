# NSS ERP — Administration Business Rules

**Document ID:** SOL-ADMIN-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the centralized
Administration and RBAC framework of the NSS ERP.

Administration is responsible for centralized:

    User Access
    Roles
    Permissions
    Organizational Scope
    Administrative Authorization

Business modules consume this framework and shall not create independent
authorization architectures.

---

# 2. Rule Classification

Each rule is classified as:

- FROZEN — established by project source
- SOURCE-ALIGNED — directly supported by existing project standards
- PENDING — requires further approval/design
- FUTURE — outside current frozen scope

---

# 3. Central RBAC

## ADMIN-BR-001 — Centralized RBAC

**Status:** FROZEN

NSS ERP shall use one centralized Role-Based Access Control framework.

The framework shall be shared by all business modules.

---

## ADMIN-BR-002 — No Module-Specific RBAC

**Status:** FROZEN

Individual business modules shall not create separate permission systems.

Examples prohibited unless explicitly approved:

    Sevak RBAC
    Attendance RBAC
    UPBS RBAC
    Membership RBAC
    Governance RBAC

All modules shall use the common ERP RBAC framework.

This principle is explicitly established in the Sevak business rules.

---

## ADMIN-BR-003 — Central Permission Matrix

**Status:** FROZEN

The detailed permission matrix shall be defined centrally within
Administration/RBAC.

Business modules identify the permissions required by their operations.

Administration owns the centralized authorization matrix.

---

# 4. User Account

## ADMIN-BR-004 — Central User Account

**Status:** FROZEN

ERP authentication accounts shall be centrally managed.

The current security foundation includes:

    user_account

The Administration module shall not create duplicate user-account entities.

---

## ADMIN-BR-005 — One Account Per ERP Identity

**Status:** SOURCE-ALIGNED

An ERP user account represents an authenticated system identity.

The account shall not be duplicated merely because the user receives
additional roles or organizational scopes.

---

## ADMIN-BR-006 — Account Deactivation

**Status:** SOURCE-ALIGNED

A user account may be deactivated when the user should no longer access the
ERP.

Deactivation shall not destroy historical records associated with the user.

---

# 5. Authentication Boundary

## ADMIN-BR-007 — Authentication vs Authorization

**Status:** FROZEN

Authentication answers:

    Who is the user?

Administration/RBAC answers:

    What may the user do?

The two responsibilities shall remain separate.

---

## ADMIN-BR-008 — No Duplicate Authentication

**Status:** FROZEN

Administration shall not create a separate authentication mechanism.

The existing Authentication & Security architecture remains authoritative.

---

# 6. Roles

## ADMIN-BR-009 — Role Definition

**Status:** SOURCE-ALIGNED

A role represents a reusable collection of application permissions.

Roles shall not be created solely as labels for individual people.

---

## ADMIN-BR-010 — Central Role Catalogue

**Status:** SOURCE-ALIGNED

Roles shall be centrally managed.

The current schema foundation includes:

    role_master

---

## ADMIN-BR-011 — Multiple Roles

**Status:** SOURCE-ALIGNED

A user may be assigned multiple roles where the authorization model permits
it.

The `user_role` relationship supports role assignment.

---

## ADMIN-BR-012 — Role Does Not Equal Person

**Status:** FROZEN

A role is an authorization concept.

It is not a Person, Membership, or Governance Position.

---

# 7. Governance Position vs Application Role

## ADMIN-BR-013 — Position and Role Are Separate

**Status:** FROZEN

Governance positions such as:

    President
    Secretary
    Parichalak

belong to the Governance domain.

Application roles belong to Administration/RBAC.

They shall not automatically be treated as the same entity.

---

## ADMIN-BR-014 — Position-Based Authorization

**Status:** SOURCE-ALIGNED

Where a Governance position results in application authority, the authority
shall be represented through the approved RBAC/mapping mechanism.

Permissions shall not be hard-coded merely from a position title.

---

# 8. Permissions

## ADMIN-BR-015 — Permission Definition

**Status:** SOURCE-ALIGNED

A permission represents an authorized system action.

The current security foundation includes:

    permission_master

---

## ADMIN-BR-016 — Permission Reuse

**Status:** FROZEN

Permissions shall be reusable across authorized roles.

A new permission shall not be created for every individual user.

---

## ADMIN-BR-017 — Permission Ownership

**Status:** FROZEN

The Administration/RBAC framework owns permission definitions.

Business modules own the business meaning of the operations being protected.

---

## ADMIN-BR-018 — No Hard-Coded Office Titles

**Status:** FROZEN

Business authorization shall not rely on hard-coded statements such as:

    President always allowed
    Secretary always allowed
    Parichalak always allowed

unless the authority has been formally represented in the RBAC model.

---

# 9. Role-Permission Assignment

## ADMIN-BR-019 — Role Permission Mapping

**Status:** FROZEN

The relationship between roles and permissions shall be centrally managed.

The current security foundation includes:

    role_permission

Conceptually:

    Role
      ↓
    Permissions

---

## ADMIN-BR-020 — Permission Revocation

**Status:** SOURCE-ALIGNED

Removing a permission from a role shall affect the user's effective access
through that role.

Historical audit records shall not be rewritten merely because current
permissions change.

---

# 10. User-Role Assignment

## ADMIN-BR-021 — User Role Assignment

**Status:** FROZEN

User-to-role assignments shall be centrally managed through:

    user_role

---

## ADMIN-BR-022 — Role Assignment Does Not Change Identity

**Status:** SOURCE-ALIGNED

Assigning or removing a role does not create a new user identity.

---

## ADMIN-BR-023 — Historical Accountability

**Status:** SOURCE-ALIGNED

Changes to role assignments shall remain attributable where auditability is
required.

A current role assignment shall not rewrite historical administrative
actions.

---

# 11. Organizational Scope

## ADMIN-BR-024 — Scope-Based Authorization

**Status:** FROZEN

Where required, authorization shall be constrained by organizational scope.

The known organizational scope levels are:

    KENDRA
    ANCHALIKA
    ZILLA
    SAKHA

---

## ADMIN-BR-025 — Central Scope Management

**Status:** SOURCE-ALIGNED

Administrative scope shall be centrally managed.

The current security foundation includes:

    admin_scope

---

## ADMIN-BR-026 — Scope Does Not Change Identity

**Status:** SOURCE-ALIGNED

Changing a user's organizational scope does not create a new Person or User
identity.

---

## ADMIN-BR-027 — Scope Does Not Change Membership

**Status:** FROZEN

Administrative authorization scope does not itself change:

    Membership
    Sangha affiliation
    Sangha Sevi ID
    Organization ownership

Those remain owned by their respective business domains.

---

# 12. Scope Levels

## ADMIN-BR-028 — Kendra Scope

**Status:** SOURCE-ALIGNED

Kendra-level authorization may provide appropriate Kendra-level oversight
according to the permission matrix.

It does not imply that every Kendra-level role has unrestricted access to
every function.

---

## ADMIN-BR-029 — Anchalika Scope

**Status:** SOURCE-ALIGNED

Anchalika-level authorization shall apply within the authorized Anchalika
scope.

---

## ADMIN-BR-030 — Zilla Scope

**Status:** SOURCE-ALIGNED

Zilla-level authorization shall apply within the authorized Zilla scope.

---

## ADMIN-BR-031 — Sakha Scope

**Status:** SOURCE-ALIGNED

Sakha-level authorization shall apply within the authorized Sakha scope.

---

# 13. Scope and Organization

## ADMIN-BR-032 — Organization Remains Authoritative

**Status:** FROZEN

The Organization module remains authoritative for the organizational
hierarchy.

Administration shall not create a duplicate organizational hierarchy.

---

## ADMIN-BR-033 — Scope Uses Existing Hierarchy

**Status:** SOURCE-ALIGNED

Administrative scope shall use the existing organizational hierarchy.

Conceptually:

    Kendra
       ↓
    Anchalika
       ↓
    Zilla
       ↓
    Sakha

The exact statutory hierarchy remains governed by the Organization
domain and authoritative governance documents.

---

## ADMIN-BR-034 — No Duplicate Organization Entities

**Status:** FROZEN

Administration shall not create duplicate:

    Kendra
    Anchalika
    Zilla
    Sakha

entities merely for authorization.

---

# 14. Effective Authorization

## ADMIN-BR-035 — Effective Access

**Status:** FROZEN

Effective access is determined through the applicable combination of:

    User
    Role
    Permission
    Organizational Scope

---

## ADMIN-BR-036 — Permission Alone May Not Be Global

**Status:** SOURCE-ALIGNED

Possession of a permission does not automatically imply unrestricted
organization-wide access where the operation is scope-sensitive.

---

## ADMIN-BR-037 — Scope Restriction

**Status:** SOURCE-ALIGNED

Where a business operation is organizationally scoped, the user's access
shall be restricted to the authorized scope.

---

# 15. Example — Sevak

## ADMIN-BR-038 — Sevak Uses Central RBAC

**Status:** FROZEN

Sevak operations shall use:

    Existing ERP RBAC
    +
    Organizational Scope

No separate Sevak permission architecture shall be introduced.

The existing Sevak rules explicitly establish this model.

---

## ADMIN-BR-039 — Sevak Scope

**Status:** FROZEN

The existing Sevak authority model identifies:

    Sakha-level user
        → Sakha-level Sevak operations

    Anchalika-level user
        → Anchalika operations

    Zilla-level user
        → Zilla operations

    Kendra-level user
        → Kendra oversight

The detailed permission matrix remains centrally defined by
Administration/RBAC.

---

# 16. Example — Business Modules

## ADMIN-BR-040 — Common Authorization Model

**Status:** SOURCE-ALIGNED

Membership, Attendance, Governance, UPBS, Sevak and other modules shall
consume the common RBAC framework.

Each module remains responsible for its own business rules.

---

# 17. Least Privilege

## ADMIN-BR-041 — Least Privilege

**Status:** SOURCE-ALIGNED

Users should receive only the permissions required for their authorized
responsibilities.

Unnecessary administrative privileges shall not be granted.

---

# 18. Administrative Separation

## ADMIN-BR-042 — High-Risk Operations

**Status:** PENDING

The current source does not define a complete catalogue of high-risk
administrative operations or mandatory segregation-of-duty rules.

These require separate RBAC/security design.

---

# 19. Super Administrator

## ADMIN-BR-043 — Super Administrator

**Status:** PENDING

A high-level administrative role may exist.

However, the current source does not freeze the complete privileges or
behaviour of a "Super Administrator".

It shall not be treated as unrestricted authority until formally defined.

---

# 20. Role Inheritance

## ADMIN-BR-044 — Role Inheritance

**Status:** PENDING

The current source does not establish a role-inheritance hierarchy.

Therefore no assumption is made that:

    Kendra Admin
        inherits
    Zilla Admin
        inherits
    Sakha Admin

or any similar relationship.

---

# 21. Permission Catalogue

## ADMIN-BR-045 — Central Permission Catalogue

**Status:** PENDING

The complete application permission catalogue has not yet been frozen.

The final catalogue must be centrally defined before implementation.

---

# 22. Permission Naming

## ADMIN-BR-046 — Consistent Permission Naming

**Status:** SOURCE-ALIGNED

Permissions shall use a consistent naming convention.

The final naming standard shall be established during detailed
Administration design.

---

# 23. User Lifecycle

## ADMIN-BR-047 — User Deactivation

**Status:** SOURCE-ALIGNED

Deactivating a user shall prevent unauthorized future access while
preserving historical accountability.

---

## ADMIN-BR-048 — Historical User Actions

**Status:** FROZEN

Deactivating a user must not erase the historical actions associated with
that user.

Audit/history must continue to identify the historical actor.

---

# 24. Role Lifecycle

## ADMIN-BR-049 — Role Changes

**Status:** SOURCE-ALIGNED

Changes to role assignments affect current authorization.

They shall not retroactively change the authorization state under which
historical actions occurred.

---

# 25. Scope Lifecycle

## ADMIN-BR-050 — Scope Changes

**Status:** SOURCE-ALIGNED

Changes to organizational scope affect future effective access.

They shall not retroactively rewrite historical activity.

---

# 26. Audit

## ADMIN-BR-051 — Administrative Auditability

**Status:** SOURCE-ALIGNED

Significant administrative changes should be auditable.

Examples include:

    User creation
    User deactivation
    Role assignment
    Role removal
    Permission assignment
    Permission removal
    Scope assignment
    Scope change

---

## ADMIN-BR-052 — Central Audit Framework

**Status:** FROZEN

Administration shall use the common Audit framework.

It shall not create a separate administration-specific audit system.

---

# 27. Audit vs Current State

## ADMIN-BR-053 — Current State Does Not Replace History

**Status:** SOURCE-ALIGNED

Current role/scope state represents the current authorization state.

Audit history represents historical administrative actions.

The two must not be treated as interchangeable.

---

# 28. Security

## ADMIN-BR-054 — Security Boundary

**Status:** SOURCE-ALIGNED

Administrative authorization shall comply with the project's common
security architecture.

---

## ADMIN-BR-055 — Password Security Boundary

**Status:** FROZEN

Password-management functionality belongs to the Authentication & Security
architecture.

The current security foundation includes:

    password_history

Administration shall not duplicate password-history management.

---

# 29. Direct Database Access

## ADMIN-BR-056 — Administrative Data Protection

**Status:** SOURCE-ALIGNED

Direct modification of RBAC data through uncontrolled database access shall
not be part of ordinary user operation.

---

# 30. Self-Authorization

## ADMIN-BR-057 — Administrative Self-Escalation

**Status:** PENDING

The current source does not freeze the complete rule for preventing an
administrator from granting themselves additional privileges.

A formal administrative security/segregation rule should be defined before
production implementation of high-risk RBAC changes.

---

# 31. Administrative Approval

## ADMIN-BR-058 — RBAC Change Approval

**Status:** PENDING

The current source does not define whether:

    Role creation
    Permission creation
    Role assignment
    Scope assignment

requires an approval workflow.

This must be established separately.

---

# 32. Governance Dependency

## ADMIN-BR-059 — Statutory Authority

**Status:** SOURCE-ALIGNED

Where administrative authority depends on organizational or governance
structure, the approved statutory and governance hierarchy takes
precedence.

The Organization governance standard states that organizational structures
must derive from authoritative statutory sources and that conflicts
must be resolved in favour of statutory authority.

---

# 33. Role and Statutory Authority

## ADMIN-BR-060 — No Permission Beyond Statutory Authority

**Status:** SOURCE-ALIGNED

Application authorization shall not be used to create authority that
contradicts the statutory organizational hierarchy.

Administrative permission cannot alter statutory ownership or reporting
relationships.

---

# 34. Organization Integrity

## ADMIN-BR-061 — Scope Cannot Break Hierarchy

**Status:** SOURCE-ALIGNED

Administrative scope assignments shall not create invalid organizational
relationships.

The Organization governance standard prohibits unauthorized hierarchy
creation, circular references, orphan units, and parallel organizational
hierarchies.

---

# 35. No Parallel Authorization Hierarchy

## ADMIN-BR-062 — One Authorization Framework

**Status:** FROZEN

NSS ERP shall maintain one central authorization framework.

Business modules may define business-level eligibility rules, but
authorization itself remains centralized.

---

# 36. Eligibility vs Authorization

## ADMIN-BR-063 — Eligibility Is Not Permission

**Status:** SOURCE-ALIGNED

Business eligibility and system authorization are separate concepts.

For example:

    Eligible to participate

does not automatically mean:

    Authorized to administer the operation.

---

# 37. Membership vs Authorization

## ADMIN-BR-064 — Membership Status Does Not Equal RBAC Role

**Status:** FROZEN

Membership status such as:

    Probationary
    Regular
    Associate

does not automatically constitute an application role.

Business modules may use membership status as an eligibility condition where
their rules require it.

---

# 38. Governance Position vs Authorization

## ADMIN-BR-065 — Governance Position Does Not Automatically Equal Permission

**Status:** FROZEN

Holding a governance position does not automatically imply every possible
application permission.

The applicable authorization must be defined through the centralized
RBAC/authority model.

---

# 39. Historical Integrity

## ADMIN-BR-066 — History Never Rewritten

**Status:** SOURCE-ALIGNED

Changes to users, roles, permissions, or scopes shall not rewrite
historical records.

---

# 40. Soft Delete

## ADMIN-BR-067 — Administrative Records

**Status:** SOURCE-ALIGNED

Where administrative entities support soft deletion, historical records
shall remain preserved.

The project-wide database standard uses:

    is_active
    deleted_at
    deleted_by_sangha_sevi_pk

for applicable transactional records.

---

# 41. No Physical Deletion of Historical Authorization Evidence

## ADMIN-BR-068 — Historical Authorization Preservation

**Status:** SOURCE-ALIGNED

Historical authorization evidence shall not be physically deleted merely
because the current role or scope is no longer active.

---

# 42. Current Security/RBAC Foundation

## ADMIN-BR-069 — Current Foundation Entities

**Status:** FROZEN

The current project schema review identifies:

    user_account
    password_history
    role_master
    permission_master
    role_permission
    user_role
    admin_scope

as the centralized Authentication & Security foundation.

Administration consumes and manages the authorization portion of this
foundation.

---

# 43. No Additional RBAC Tables Assumed

## ADMIN-BR-070 — Current Scope Boundary

**Status:** FROZEN

The following are not currently frozen:

    role_history
    scope_history
    permission_group
    role_inheritance
    user_permission
    admin_action
    admin_approval

They require separate approved requirements.

---

# 44. Administrative Dashboard

## ADMIN-BR-071 — Authorized Dashboard

**Status:** SOURCE-ALIGNED

The Administration Dashboard shall only expose functions permitted to the
current user.

The dashboard shall not itself bypass RBAC.

---

# 45. UI Cannot Override RBAC

## ADMIN-BR-072 — Server-Side Authorization

**Status:** SOURCE-ALIGNED

Hiding a UI button is not sufficient authorization enforcement.

The backend/API shall independently enforce the applicable permission and
scope.

---

# 46. API Authorization

## ADMIN-BR-073 — API Must Enforce RBAC

**Status:** SOURCE-ALIGNED

Administrative API operations shall enforce:

    Authentication
    Permission
    Organizational Scope

The UI shall not be treated as the security boundary.

---

# 47. Database Authorization

## ADMIN-BR-074 — Database Integrity

**Status:** SOURCE-ALIGNED

Database constraints shall protect structural RBAC integrity.

Application-level authorization remains responsible for determining whether
a user may perform an operation.

---

# 48. Centralized Enforcement

## ADMIN-BR-075 — One Authorization Decision

**Status:** SOURCE-ALIGNED

A user's effective authorization should be determined consistently across:

    UI
    API
    Backend Services

Different layers shall not implement contradictory authorization rules.

---

# 49. Rule Summary

| Area | Status |
|---|---|
| Centralized RBAC | FROZEN |
| No Module-Specific RBAC | FROZEN |
| Central Permission Matrix | FROZEN |
| Central User Accounts | FROZEN |
| Roles | SOURCE-ALIGNED |
| Permissions | SOURCE-ALIGNED |
| User-Role Assignment | FROZEN |
| Role-Permission Assignment | FROZEN |
| Organizational Scope | FROZEN |
| Kendra Scope | SOURCE-ALIGNED |
| Anchalika Scope | SOURCE-ALIGNED |
| Zilla Scope | SOURCE-ALIGNED |
| Sakha Scope | SOURCE-ALIGNED |
| Organization Owns Hierarchy | FROZEN |
| Position ≠ Application Role | FROZEN |
| Membership ≠ Application Role | FROZEN |
| Central Audit | FROZEN |
| Least Privilege | SOURCE-ALIGNED |
| Role Inheritance | PENDING |
| Permission Catalogue | PENDING |
| High-Risk Segregation | PENDING |
| RBAC Change Approval | PENDING |
| Self-Escalation Rule | PENDING |
| Role History | PENDING |
| Scope History | PENDING |

---

# 50. Core Administration Principle

The central Administration rule is:

    Authorization is centralized,
    scope-aware,
    permission-based,
    and independent of individual business-module RBAC systems.

---

# 51. Effective Authorization Model

```text
Authenticated User
        │
        ▼
   user_account
        │
        ├──────────────┐
        ▼              ▼
    user_role      admin_scope
        │              │
        ▼              │
   role_master         │
        │              │
        ▼              │
 role_permission       │
        │              │
        ▼              │
permission_master      │
        │              │
        └──────┬───────┘
               ▼
      Effective Authorization
               │
               ▼
       Business Operation
```

---

# 52. Status

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
