# NSS ERP — Organization Module Overview

**Document ID:** SOL-ORG-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Organization  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Organization Module defines and maintains the organizational structure of NSS within the ERP.

Its purpose is to ensure that the ERP represents:

- Statutoryly recognized organizational units
- Organizational hierarchy
- Parent-child relationships
- Organizational identity
- Organizational status
- Organizational lineage
- Organizational address information
- Organizational scope used by other ERP modules

The module provides the organizational foundation on which Governance, Membership, Attendance, Sevak, Mahila, Kumari, Kishori, Kishor, Reports, Administration, and other modules depend.

---

# 2. Governing Authority

The Organization Module shall follow the approved:

**GOV-002 — Organizational Governance Standard**

The NSS Bye-Law is the supreme governing authority for organizational structures represented in the ERP.

Where this solution documentation conflicts with an authoritative statutory document, the authoritative statutory document prevails.

---

# 3. Organizational Governance Principle

The ERP shall represent the statutory organizational hierarchy rather than creating an independent ERP-specific hierarchy.

Organizational authority shall flow through the approved statutory structure.

No ERP feature shall create an organizational relationship that contradicts the authoritative hierarchy.

---

# 4. Single Apex Organization

The Organization Module shall maintain one apex organization.

The apex organization:

- Has no parent organization
- Is the root of the organizational hierarchy
- Provides statutory authority for subordinate organizational units
- Is unique within the ERP

Only one apex organization shall exist in the production organizational hierarchy.

---

# 5. Organizational Unit

An organizational unit is a statutorily recognized organizational entity represented within the ERP.

Each organizational unit shall:

- Have a unique organizational identity
- Have exactly one parent unless it is the apex
- Belong to the statutory hierarchy
- Have an organizational type
- Have an organizational status
- Remain traceable to the apex

---

# 6. Organizational Hierarchy

The Organization Module represents a parent-child hierarchy.

Conceptually:

```text
Apex Organization
        │
        ├── Child Organization
        │       │
        │       ├── Child Organization
        │       └── Child Organization
        │
        └── Child Organization
```

Every non-apex organization shall have one immediate parent.

---

# 7. Organizational Lineage

The complete lineage of an organization shall be traceable from that organization to the apex.

Example:

```text
Organization
    ↓
Parent Organization
    ↓
Higher Parent
    ↓
Apex Organization
```

Reports, permissions, workflows, and organizational filtering may rely on this lineage.

---

# 8. Parent-Child Integrity

The ERP shall prohibit:

* Multiple parents
* Circular references
* Orphan organizations
* Invalid hierarchy transitions
* Parallel independent organizational trees

The parent-child relationship is a core organizational integrity rule.

---

# 9. Permanent Organizational Identity

Every organizational unit shall receive a permanent system-generated identifier.

The identifier shall:

* Be unique
* Remain immutable
* Never be reused
* Be referenced consistently across ERP modules

This requirement is explicitly established by the Organizational Governance Standard. 

---

# 10. Organizational Lifecycle

Organizations follow a controlled lifecycle.

The approved governance standard identifies typical lifecycle states:

```text
PROPOSED
APPROVED
ACTIVE
INACTIVE
ARCHIVED
```

Lifecycle transitions shall occur only through approved organizational governance procedures. 

The exact transition matrix belongs in the Organization Lifecycle document.

---

# 11. Organizational Status

The current organization design uses a dedicated:

```text
organization_status_master
```

for controlled organization status values.

Status shall not be represented through arbitrary free text.

---

# 12. Organizational Type

The current Organization design uses:

```text
organization_type_master
```

to classify organizational units.

This allows the organization hierarchy to remain data-driven rather than hard-coded into application logic.

---

# 13. Current Organization Table Scope

The current revised Organization foundation consists of three tables:

```text
organization_type_master

organization_status_master

organization
```

This three-table scope is recorded in the project source. 

---

# 14. Organization Type Master

`organization_type_master` defines the controlled classifications of organizational units.

The exact final statutory organization-type values shall be derived from approved authoritative organizational references.

The ERP shall not invent statutory organizational levels.

---

# 15. Organization Status Master

`organization_status_master` defines the controlled lifecycle/status classifications used by organizations.

The master supports controlled organizational lifecycle management.

---

# 16. Organization

The `organization` table represents the actual organizational units.

It is the central entity of the Organization Module.

Conceptually:

```text
organization_type_master
          │
          ▼
     organization
          ▲
          │
organization_status_master
```

---

# 17. Organization Self-Hierarchy

The organization entity contains the parent relationship required to represent the organizational hierarchy.

Conceptually:

```text
organization
     │
     └── parent_organization
              │
              └── parent_organization
```

The hierarchy shall terminate at the single apex organization.

---

# 18. Organizational Address

The current project design establishes:

```text
One organization
→ One address record maximum
```

The current v1 design does not introduce a separate `organization_address` table.

Address information is stored directly within `organization`. 

---

# 19. Organization Address Fields

The revised organization design identifies address information including:

```text
address_line_1
address_line_2
district_pk
state_pk
country_pk
postal_code
```

These are organization attributes rather than a separate address entity in the current design. 

---

# 20. Address History

The current Organization design does not introduce organization address history.

The current rule is:

```text
One organization
→ One current address
```

No separate address-history table is part of the current frozen scope.

---

# 21. Anchalika and Zilla

The project source distinguishes organizational concepts according to NSS reality.

In particular:

```text
KENDRA          = Central Body (unique)
NILACHALA_KUTIRA = Spiritual Residence (unique)
SMRUTI_MANDIRA  = Memorial Temple (unique)
ANCHALIKA       = Administrative Unit (multiple)
ZILLA           = Administrative Unit (multiple)
SAKHA           = Physical Sangha Location (multiple)
SAKHA_ASANA     = Approved Sakha, no own building (multiple)
PATHA_CHAKRA    = Study Circle (multiple)
```

Therefore an Anchalika or Zilla should not automatically be treated as having a physical address equivalent to a Sakha. 

---

# 22. Sakha

A Sakha is treated as a physical Sangha location within the organizational model.

Its organizational record may therefore carry physical address information.

---

# 23. Organization Module Does Not Own Membership

The Organization Module does not determine whether a person is:

* Probationary Member
* Regular Member
* Associate Member
* Non-member

Those are Membership-domain concepts.

Organization provides the organizational context.

---

# 24. Organization Module Does Not Own Person

The Organization Module does not duplicate the Person database.

Person identity belongs to the Person Module.

Organization may be referenced by Person, Membership, Governance, Attendance, and other modules.

---

# 25. Organization Module Does Not Own Governance Positions

The Organization Module establishes organizational units.

The Governance Module owns:

* Governing bodies
* Positions
* Office-bearer assignments
* Terms
* Elections
* Governance workflows

---

# 26. Organization Module Does Not Own Attendance

Attendance may use organizational scope, but attendance records and attendance rules remain owned by the Attendance Module.

---

# 27. Organization as Cross-Module Foundation

Many modules depend on organization context.

Examples include:

```text
Person
Membership
Attendance
Governance
Sevak
Mahila
Kumari
Kishori
Kishor
UPBS
Reports
Administration
```

The Organization Module therefore provides foundational organizational identity and scope.

---

# 28. Organizational Scope

Organizational scope may be used to determine what records a user or administrative role can access.

For example:

```text
Sakha scope
Anchalika scope
Zilla scope
Kendra scope
```

The exact authorization matrix belongs to Administration/RBAC.

---

# 29. Organizational Authority

Organizational authority shall follow the statutory hierarchy.

No organization may exercise authority beyond what is granted by the applicable statutory or governance framework.

---

# 30. Delegated Authority

Administrative delegation may allow operational management of organizational records.

Delegation shall not change statutory ownership or parent-child relationships.

Delegated authority shall remain auditable.

---

# 31. Organizational Independence Restriction

An organizational unit shall not operate outside the statutory hierarchy.

The ERP shall prohibit:

* Unauthorized hierarchy creation
* Unauthorized restructuring
* Duplicate statutory entities
* Parallel organizational hierarchies
* Unsupported governance relationships

---

# 32. Duplicate Organization Prevention

The system shall prevent duplicate representations of the same statutorily recognized organizational unit.

Organizational identity must remain unique and permanent.

---

# 33. Organizational Identifier

The organization identifier shall be generated by the system.

It shall not be manually reused or reassigned.

The identifier shall remain stable throughout the organization's lifecycle.

---

# 34. Organizational Status vs Organizational Type

These are separate concepts.

```text
Organization Type
        ≠
Organization Status
```

Example:

```text
Type:
SAKHA

Status:
ACTIVE
```

An organization's type identifies what it is.

Its status identifies its lifecycle state.

---

# 35. Organizational Type vs Hierarchical Level

The Organization Module shall not assume that every organization type automatically implies an arbitrary hierarchy.

The statutory source determines valid organizational relationships.

---

# 36. Statutory Authority

Only approved authoritative references may establish or modify statutory organizational structure.

The ERP shall not create new statutory organizational levels merely for software convenience.

---

# 37. Organizational Change

Changes to the organizational hierarchy shall follow the approved governance change process.

Examples:

* Creation of a statutorily recognized organization
* Closure of an organization
* Approved restructuring
* Parent reassignment
* Organizational status transition

Such changes must preserve historical traceability.

---

# 38. Organizational History

Organizational history shall be preserved.

Changes to organizational status or structure shall not destroy the permanent identity of the organization.

---

# 39. Parent Change

A parent relationship shall not be changed casually.

Any valid parent change must be supported by the applicable authoritative organizational/governance decision.

The previous organizational lineage must remain traceable according to the project's history/audit standards.

---

# 40. Organizational Status Changes

Status changes shall follow controlled lifecycle rules.

Example conceptual lifecycle:

```text
PROPOSED
    ↓
APPROVED
    ↓
ACTIVE
    ↓
INACTIVE
    ↓
ARCHIVED
```

The exact allowed transitions shall be defined in `03_organization_lifecycle.md`.

---

# 41. Archived Organizations

An archived organization remains historically identifiable.

Archiving shall not reuse its organizational identifier.

---

# 42. Inactive Organizations

An inactive organization remains part of organizational history.

Inactive status shall not imply deletion.

---

# 43. Organizational Reporting

The Organization Module shall support reporting based on:

* Organization
* Organization type
* Organization status
* Parent
* Children
* Organizational lineage

---

# 44. Hierarchy Navigation

Authorized users should be able to navigate:

```text
Apex
  ↓
Parent
  ↓
Child
  ↓
Sub-child
```

without ambiguity.

---

# 45. Organization Search

The Organization Module should support searching by relevant organization information, including:

* Organization ID
* Organization name
* Organization type
* Organization status
* Parent organization
* Geographic information where applicable

---

# 46. Organization Address Boundary

The current design deliberately avoids:

```text
organization_address
```

as a separate table.

Instead:

```text
organization
    ├── address_line_1
    ├── address_line_2
    ├── district_pk
    ├── state_pk
    ├── country_pk
    └── postal_code
```

This reflects the current project decision. 

---

# 47. Location Master Integration

Where location references are required, Organization should use the common Location Master framework.

The Organization Module shall not create duplicate:

```text
Country
State
District
City
PIN
```

masters.

---

# 48. Physical Address Rule

The current Organization design permits one address directly on the organization.

It does not establish multiple active addresses.

---

# 49. No Address History Table

The current v1 Organization scope does not include:

```text
organization_address
organization_address_history
```

---

# 50. Auditability

Organization changes shall be auditable.

At minimum, the system shall preserve traceability for:

* Creation
* Status changes
* Parent changes
* Organizational changes
* Administrative modifications

---

# 51. Security

Organization administration shall use the common:

```text
Authentication
RBAC
Organizational Scope
Audit
```

framework.

No separate Organization authentication system shall be created.

---

# 52. Administrative Responsibilities

Authorized administrators may manage organizational records according to their organizational scope.

The exact permission matrix belongs to the Administration/RBAC module.

---

# 53. Public Visibility

Not every organizational record necessarily requires public visibility.

Public presentation of organizational information shall follow the applicable module and access rules.

---

# 54. Data Integrity

The Organization Module shall maintain:

```text
Single Apex
Valid Parent
No Cycles
No Orphans
Unique Identity
Stable Identifier
Valid Type
Valid Status
Traceable Lineage
```

---

# 55. Database and Application Enforcement

Organizational integrity shall be enforced through both:

```text
Database Constraints
+
Application Validation
```

The Governance Standard explicitly requires parent-child integrity enforcement through database constraints and application validation. 

---

# 56. No Parallel Organizational Trees

A production Organization hierarchy shall not contain multiple independent organizational roots.

All organizations must ultimately trace to the single apex.

---

# 57. No Circular Relationships

The system shall prohibit:

```text
A → B
B → C
C → A
```

Circular organizational relationships are invalid.

---

# 58. No Orphan Organizations

Every non-apex organization shall reference one valid parent organization.

---

# 59. No Multiple Parents

An organizational unit shall not simultaneously belong to multiple parents within the statutory hierarchy.

---

# 60. Organization Module Boundaries

The Organization Module owns:

```text
Organizational Identity
Organizational Type
Organizational Status
Parent-Child Hierarchy
Organizational Lineage
Organization Address
```

It does not own:

```text
Person Identity
Membership
Governance Positions
Attendance
Finance
Document Storage
Authentication
```

---

# 61. Current Three-Table Foundation

```text
organization_type_master
        │
        ▼
organization
        ▲
        │
organization_status_master
```

The organization hierarchy is represented within `organization`.

---

# 62. Current Scope Exclusions

The current Organization design does not introduce separate tables for:

```text
organization_hierarchy
organization_address
sakha_sangha
mahila_sangha
sikshya_kendra
sakha_asana
paribarik_asana
patha_chakra
```

unless future authoritative requirements explicitly require them.

This is important because older schema proposals contained several of these tables, while the later project source records the reduced three-table Organization scope. 

---

# 63. Organization and Specialized Modules

Specialized modules may maintain domain-specific information related to an organization.

For example:

```text
Mahila
Sevak
Kumari
Kishori
Kishor
```

Such modules shall reference the Organization Module rather than duplicate the organizational master.

---

# 64. Organization and Mahila

Mahila-specific organizational/governance information shall follow the approved Mahila documentation.

The Organization Module remains the authoritative source for the underlying organization identity where an organizational entity is represented in the common hierarchy.

---

# 65. Organization and Sevak

Sevak operations use organizational scope.

The Sevak Module shall reference Organization rather than create a second organization hierarchy.

---

# 66. Organization and Membership

Membership records may associate a member with an organizational context.

The Organization Module remains authoritative for the organization itself.

---

# 67. Organization and Person

A Person may interact with one or more organizational contexts through membership, governance, participation, or other relationships.

The Organization Module does not duplicate Person information.

---

# 68. Organization and Governance

Governance positions are attached to organizational contexts.

Governance remains responsible for office-bearer and position management.

---

# 69. Organization and Reports

Reports may traverse organizational lineage.

For example:

```text
Kendra
  ↓
Zilla
  ↓
Anchalika
  ↓
Sakha
```

where such levels are established by the authoritative organizational structure.

---

# 70. Organization and RBAC

RBAC may use organizational scope to determine access.

For example:

```text
Sakha User
    ↓
Sakha Scope

Zilla User
    ↓
Zilla Scope

Kendra User
    ↓
Kendra Scope
```

The exact permissions are centrally governed by Administration/RBAC.

---

# 71. Organization Lifecycle Ownership

The Organization Module owns the lifecycle of organizational records.

Other modules may react to organizational status changes but shall not independently redefine organizational lifecycle.

---

# 72. Historical Preservation

Organizational history shall remain traceable.

The ERP shall preserve:

```text
Organization Identity
Parent Relationships
Status History
Relevant Administrative Changes
```

according to the common audit/history framework.

---

# 73. Statutory Compliance

All organizational solution artifacts must comply with GOV-002.

Any deviation requires formal governance approval.

The Governance Standard states that compliance is mandatory across requirements, schemas, APIs, UI, workflows, reports, and administrative functions. 

---

# 74. Documentation Sequence

The Organization documentation set is:

```text
01_organization_module_overview.md
02_organization_erd.md
03_organization_lifecycle.md
04_organization_business_rules.md
05_organization_table_design.md
```

Each document has a separate responsibility.

---

# 75. Documentation-First Principle

The current work is Solution documentation only.

No SQL schema is being created.

The sequence remains:

```text
Authoritative Source
        ↓
Module Overview
        ↓
ERD
        ↓
Lifecycle
        ↓
Business Rules
        ↓
Table Design
        ↓
Physical Database
```

---

# 76. Current Frozen Foundation

The current Organization foundation is:

```text
organization_type_master
organization_status_master
organization
```

with the organization hierarchy represented through the organization entity and its parent relationship.

---

# 77. Final Organization Architecture

```text
                    ORGANIZATION MODULE
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
       Organization     Organization   Organization
           Type            Status        Entity
           Master          Master          │
                                           │
                                           ├── Parent
                                           ├── Identity
                                           ├── Address
                                           └── Lineage
```

---

# 78. Core Principles

The Organization Module shall preserve:

```text
✓ One statutory apex
✓ Exactly one parent for every non-apex organization
✓ No circular hierarchy
✓ No orphan organizations
✓ Permanent organizational identity
✓ Immutable organizational identifier
✓ Traceable organizational lineage
✓ Controlled organization lifecycle
✓ Master-driven organization type
✓ Master-driven organization status
✓ One current address maximum in current v1 design
✓ Common location master reuse
✓ Common RBAC reuse
✓ Common audit reuse
✓ Statutory authority precedence
✓ No unauthorized organizational levels
✓ No duplicate organizational hierarchy
```

---

# 79. Future Changes

Any future change to the statutory organizational model shall first be supported by an approved authoritative source or formal governance decision.

The Solution documentation shall then be updated before physical implementation.

---

# 80. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
