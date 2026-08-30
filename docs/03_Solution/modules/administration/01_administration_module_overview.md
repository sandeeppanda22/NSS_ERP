# NSS ERP — Administration Module Overview

**Document ID:** SOL-ADMIN-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Administration Module provides the centralized administrative control
framework for the NSS ERP.

Its primary responsibility is to manage:

    Users
    Roles
    Permissions
    Organizational Scope
    Administrative Access
    System Administration

Administration provides the common authorization framework used by the
other ERP modules.

---

# 2. Module Position

Administration is a top-level NSS ERP module.

The frozen module hierarchy includes:

    Foundation
    Membership
    Family
    Governance
    Attendance
    Mahila Sangha
    Kumari Sangha
    Kishor Puja
    Sevak Sangha
    Founder & Heritage
    Publications
    UPBS
    Reports & Analytics
    Administration

Administration is therefore a system-wide module rather than a
module-specific permission system.

---

# 3. Django Application

The project application structure includes:

    backend/apps/administration

Administration therefore has its own Django application.

---

# 4. Primary Responsibilities

The Administration Module is responsible for centralized management of:

    User Access
    Roles
    Permissions
    Organizational Scope
    Administrative Configuration
    Access Governance

---

# 5. Central RBAC Principle

The NSS ERP shall use a centralized RBAC architecture.

Conceptually:

```text
User
  │
  ▼
Role
  │
  ▼
Permission
  │
  ▼
Authorized Action
```

Modules shall not create independent permission systems unless explicitly
approved.

---

# 6. Organizational Scope

Authorization is not based only on role.

It also depends on organizational scope where applicable.

The established scope levels include:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

Therefore:

```text
User
  │
  ├── Role
  │
  └── Organizational Scope
          │
          ▼
     Effective Access
```

---

# 7. Role + Scope Model

A user's effective authority is determined through:

```
Identity
+
Role
+
Organizational Scope
+
Permission
```

The exact permission matrix is centrally defined through Administration.

---

# 8. No Module-Specific RBAC

Business modules shall not create independent permission architectures.

For example, the Sevak Module explicitly uses:

```
Existing ERP RBAC
+
Organizational Scope
```

and states that the detailed permission matrix is centrally defined in the
Administration/RBAC module.

---

# 9. Example — Sevak

A Sevak operation may be authorized according to:

```text
Sakha-level user
    → Sakha-level Sevak operations

Anchalika-level user
    → Anchalika operations

Zilla-level user
    → Zilla operations

Kendra-level user
    → Kendra oversight
```

The Sevak Module does not define its own permission architecture.

---

# 10. Example — Administration

Administration itself manages the authorization framework but does not
automatically grant every administrator unrestricted access to every ERP
function.

Administrative access must itself be governed.

---

# 11. User Management

Administration provides the central administrative capability for managing
ERP users.

Conceptually:

```text
Person / Identity
        │
        ▼
      User
        │
        ▼
      Role
        │
        ▼
   Permissions
```

The exact identity relationship is owned jointly by the existing
Authentication and Administration architecture.

---

# 12. Authentication Boundary

Authentication and Administration are related but have different
responsibilities.

Authentication handles:

```
Login
Identity Verification
Session
Authentication State
```

Administration handles:

```
Roles
Permissions
Administrative Access
Organizational Scope
```

---

# 13. No Duplicate Authentication

Administration shall not create a separate authentication mechanism.

It shall reuse the centralized Authentication architecture.

---

# 14. Role Management

Administration provides the central framework for defining and managing ERP
roles.

A role represents a reusable authorization grouping.

Examples already present in the UI/security baseline include concepts such
as:

```
Member
Secretary
President
Parichalak
Kendra Office
Administrator
```

These examples must not automatically be treated as the complete frozen
role catalogue.

---

# 15. Permission Management

Permissions represent actions that a role may perform.

Conceptually:

```text
Role
  │
  ├── Permission A
  ├── Permission B
  └── Permission C
```

The final permission catalogue requires detailed RBAC design.

---

# 16. Role-Permission Relationship

The existing project schema planning identifies:

```
role_permission
```

as part of the security/RBAC foundation.

Administration owns the centralized permission-management concept.

---

# 17. User-Role Relationship

The existing project schema planning identifies:

```
user_role
```

as part of the centralized RBAC foundation.

This represents assignment of roles to users.

---

# 18. Administrative Scope

The existing project schema planning identifies:

```
admin_scope
```

for scope-based access.

The known organizational scopes are:

```
KENDRA
ANCHALIKA
ZILLA
SAKHA
```

---

# 19. Scope-Based Authorization

A permission alone does not necessarily mean global access.

Example:

```text
Permission:
    MEMBER_VIEW

Scope:
    SAKHA A
```

means the user may view members within the authorized Sakha scope rather
than automatically viewing all members in the ERP.

---

# 20. Kendra Scope

Kendra-level authorization may provide oversight across the appropriate
organizational hierarchy.

Exact permission boundaries require the centralized RBAC matrix.

---

# 21. Anchalika Scope

Anchalika-level authorization applies within the authorized Anchalika
scope.

It shall not automatically imply unrestricted Kendra-wide access.

---

# 22. Zilla Scope

Zilla-level authorization applies within the authorized Zilla scope.

The exact hierarchy and inheritance rules follow the organizational model.

---

# 23. Sakha Scope

Sakha-level authorization applies within the authorized Sakha scope.

This is especially important for daily operational users such as Sakha-level
administrators/office bearers.

---

# 24. Organizational Hierarchy Dependency

Administration relies on the authoritative Organization module for the
organizational hierarchy.

It shall not create a second organizational hierarchy.

Conceptually:

```text
Organization
     │
     ▼
Organizational Scope
     │
     ▼
Administration / RBAC
     │
     ▼
Effective Access
```

---

# 25. Role Does Not Replace Office-Bearer Position

A Governance position such as:

```
President
Secretary
Parichalak
```

is a governance/business concept.

An application role is an authorization concept.

These must not automatically be treated as the same entity.

---

# 26. Position-to-Role Mapping

Where a governance position results in application authority, the mapping
shall be explicitly defined.

The system shall not hard-code permissions solely from the display name of
an office-bearer position.

---

# 27. Centralized Permission Matrix

The final permission matrix shall be centrally maintained.

Modules should specify:

```
Required Permission
```

rather than defining their own authorization logic.

---

# 28. Example Permission Concept

Conceptually:

```text
MEMBERSHIP_MEMBER_VIEW
MEMBERSHIP_MEMBER_EDIT
ATTENDANCE_MARK
ATTENDANCE_REVIEW
GOVERNANCE_MANAGE
UPBS_REGISTRATION_MANAGE
SEVAK_ENROLL
REPORT_VIEW
```

These are examples of permission concepts only.

The final permission catalogue remains a separate RBAC design decision.

---

# 29. Least Privilege

Administrative access should follow the principle of least privilege.

A user should receive only the permissions required for their authorized
responsibilities.

---

# 30. Scope Restriction

A permission should be constrained by organizational scope wherever the
business operation requires scope restriction.

---

# 31. Administrative Separation

High-risk administrative operations may require stronger authorization than
ordinary operational functions.

The exact approval/separation rules require detailed Administration/RBAC
design.

---

# 32. Super Administrator

A high-level administrative role may exist for technical/system
administration.

However, the existence of a "Super Admin" concept in the UI baseline does
not by itself define the complete authorization policy.

The final role catalogue must be formally established.

---

# 33. Administrative Dashboard

The UI roadmap includes an:

```
Administration Dashboard
```

for authorized administrative users.

The dashboard should provide centralized visibility into administrative
functions.

The exact widgets and metrics are UI-design concerns.

---

# 34. Administration Navigation

Administration appears as a top-level item in the frozen UI navigation.

Conceptually:

```text
Administration
    │
    ├── Users
    ├── Roles
    ├── Permissions
    └── Scope
```

Additional screens require detailed UI design.

---

# 35. User Lifecycle

User lifecycle management should distinguish between:

```
User Identity
Authentication Status
Role Assignment
Scope Assignment
```

These are separate concepts.

---

# 36. User Deactivation

Deactivating a user should not destroy historical business or audit records
associated with that user.

Historical actions must remain attributable.

---

# 37. Role Changes

Changes to a user's role shall not erase historical role assignments or
historical audit information where such history is required.

The final role-history model requires detailed design.

---

# 38. Scope Changes

Changes to organizational scope shall preserve historical accountability.

A user's current scope must not retroactively rewrite the scope under which
a previous action was performed.

---

# 39. Audit Integration

Administrative actions may require centralized Audit records.

Examples:

```
User creation
User deactivation
Role assignment
Permission changes
Scope changes
High-risk administrative changes
```

The Audit Module remains the centralized audit authority.

---

# 40. No Duplicate Audit System

Administration shall not create a separate:

```
administration_audit
```

system.

The common Audit framework shall be reused.

---

# 41. Security Integration

Administration is closely integrated with:

```
Authentication
RBAC
Organization
Audit
```

but remains a separate business/system responsibility.

---

# 42. Administration and Organization

Organization owns:

```
Kendra
Anchalika
Zilla
Sakha
Organizational hierarchy
```

Administration owns:

```
Scope assignment
Access rules
Administrative authorization
```

---

# 43. Administration and Person

Person remains the authoritative person identity.

Administration does not create a duplicate administrative-person entity.

---

# 44. Administration and Membership

Membership determines NSS membership identity/status.

Administration determines application authorization.

Membership status may influence eligibility for certain roles or operations
where explicitly defined, but Administration does not become the owner of
membership status.

---

# 45. Administration and Governance

Governance owns:

```
Bodies
Positions
Assignments
Elections
Governance history
```

Administration owns:

```
Application permissions
Role assignments
Administrative scope
```

The two concepts must remain distinct.

---

# 46. Administration and Reports

Reports may expose administrative/security information only to authorized
users.

Administration provides the authorization boundary.

Reports remains responsible for reporting.

---

# 47. Administration and Notifications

Administrative actions may trigger notifications where required.

Notifications use the common Notification framework.

Administration does not create a separate notification engine.

---

# 48. Configuration Boundary

The ERP follows:

```
Configuration Over Hardcoding
```

Where administrative settings are intended to be configurable, they should
use the approved Foundation/System Settings architecture rather than
hard-coded application logic.

---

# 49. Foundation Dependency

Foundation provides common system-level capabilities such as:

```
Master Data
System Settings
ID Sequences
```

Administration consumes these capabilities where appropriate.

Administration does not duplicate Foundation.

---

# 50. Security Boundary

Administration is not the same as Security.

Security provides broader technical/security architecture.

Administration provides operational management of:

```
Users
Roles
Permissions
Scope
```

The two areas must remain coordinated.

---

# 51. No Duplicate Organization Hierarchy

Administration shall not create:

```
admin_kendra
admin_anchalika
admin_zilla
admin_sakha
```

as duplicate organizational entities.

The Organization module remains authoritative.

---

# 52. No Module-Specific Permission Tables

Business modules shall not independently create:

```
sevak_role
upbs_role
attendance_role
membership_role
```

or similar permission systems.

Central RBAC remains authoritative.

---

# 53. Historical Integrity

Administrative history shall remain traceable.

Changes to access control must not silently erase evidence of prior
authorization states.

---

# 54. Administrative Accountability

High-impact administrative changes shall be attributable to the authorized
administrator who performed them.

This supports the project's broader auditability principle.

---

# 55. Current Scope

The Administration Module currently covers:

```text
Users
Roles
Permissions
Organizational Scope
RBAC
Administrative Access
Administration Dashboard
Correspondence Register
```

---

# 56. Correspondence Register Capability

**CORR-DECISION-003 — Administration Correspondence Register**

Administration owns the official correspondence register for inward and outward communications.

## 56.1 Scope

```text
Administration
└── Correspondence Register
    ├── Inward correspondence (received)
    └── Outward correspondence (sent)
```

## 56.2 What Correspondence Register Covers

- Registration of official inward/outward communications
- Reference numbering (sequential per financial year)
- Sender/recipient information
- Subject and date
- Medium (post, email, hand-delivery, circular)
- Responsible person/office
- Status/follow-up information
- Association with Foundation-owned documents (`document_master`)

## 56.3 Ownership Boundaries

The correspondence register records official communications. It does not own the underlying business matter:

```text
Government property-tax letter
        ↓
Administration correspondence register (records the communication)
        ↓
Assets & Property (property context)
        ↓
Finance (payment transaction)
```

Domain-specific business requests remain with their owning modules:

- Membership renewal/transfer → Membership
- Gruhasana renewal → Membership
- Financial transactions → Finance
- Property matters → Assets & Property
- Governing-body decisions → Governance

## 56.4 What Correspondence Register Does Not Provide

- Generic form/application engine
- Domain-specific request workflows
- BPM/workflow automation
- Email/messaging system
- Duplicate of domain-owned request lifecycles

## 56.5 Architecture Status

- Capability: **ACCEPTED** (CORR-DECISION-003)
- Detailed ERD/lifecycle/business rules/table design: **TO BE DOCUMENTED**
- Physical tables: **NOT YET FROZEN**

---

# 57. Current Source-Supported RBAC Foundation

The existing project source identifies the following security/RBAC concepts:

```
role_permission
user_role
admin_scope
```

The detailed complete Administration schema is not yet declared frozen by
this overview.

---

# 58. Tables Not Assumed

This overview does NOT freeze additional tables such as:

```
role_history
permission_group
user_scope_history
admin_action
admin_setting
session_management
```

unless supported by subsequent approved design.

---

# 59. Administrative Principle

The central Administration principle is:

```
Centralize authorization; do not duplicate it across modules.
```

---

# 60. Architecture Summary

```text
                    Authentication
                          │
                          ▼
                         User
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
           Role                     Scope
             │                         │
             └────────────┬────────────┘
                          ▼
                     Permissions
                          │
                          ▼
                  Effective Access
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
      Membership      Attendance       UPBS
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                        Audit
```

---

# 61. Design Boundary

This overview establishes:

```
Administration Scope
Central RBAC Principle
Role/Permission Concept
Organizational Scope Concept
Authentication Boundary
Organization Boundary
Audit Boundary
Module Authorization Boundary
```

It does not yet freeze:

```
Complete Role Catalogue
Complete Permission Catalogue
Role Inheritance
Scope Inheritance
Role History Tables
Permission Grouping
Administrative Approval Workflow
Detailed User Lifecycle
Detailed Physical Schema
```

---

# 62. Source Alignment

The frozen NSS module hierarchy explicitly identifies Administration as a
top-level ERP module and includes:

```
backend/apps/administration
```

in the Django application structure.

The project source identifies Administration as responsible for:

```
Users
Roles
Permissions
```

and the security/RBAC planning identifies:

```
role_permission
user_role
admin_scope
```

as part of the access-control foundation.

The Sevak business rules explicitly state that module operations use the
existing ERP RBAC plus organizational scope and that the detailed permission
matrix is defined centrally in the Administration/RBAC module.

---

# 63. Status

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
