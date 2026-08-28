# NSS ERP — Organization Business Rules

**Document ID:** SOL-ORG-004  
**Version:** 1.1.0  
**Status:** DRAFT — GOVERNANCE ALIGNED  
**Module:** Organization  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing organizational entities
within the NSS ERP.

The rules cover:

- Statutory organizational authority
- Organizational identity
- Organizational hierarchy
- Parent-child integrity
- Organizational lineage
- Hierarchical level
- Organizational lifecycle
- Organizational authority
- Delegated authority
- Organizational independence
- Organizational status
- Organizational change control
- Cross-module organizational consistency

The primary governing source is:

```text
GOV-002 — Organizational Governance Standard
```

The NSS Bye-Law remains the supreme governing authority for all
organizational structures represented in the ERP.

Where a conflict exists between this solution document and an authoritative
statutory source, the statutory source prevails.

---

# 2. Rule Identification

Organization business rules use:

```text
ORG-BR-001
ORG-BR-002
ORG-BR-003
...
```

Where a rule directly corresponds to a GOV-002 rule, the corresponding
governance identifier is retained in the traceability section.

---

# 3. Statutory Authority

## ORG-BR-001 — Statutory Authority Precedence

The organizational hierarchy implemented by the ERP shall be derived from
approved statutory and authoritative reference documents.

Business rules, workflows, permissions, reports, APIs, UI, and organizational
metadata shall not contradict statutory authority.

Where a conflict exists:

```text
Statutory Authority
        ↓
takes precedence
```

This directly implements GOV-ORG-002.

---

## ORG-BR-002 — Authoritative Source Requirement

Only authoritative documents recognized through AUTH-001 shall be used to
define, modify, or validate organizational structures.

Unapproved documents shall not be treated as authoritative organizational
sources.

Any proposed organizational change shall undergo the applicable governance
review process before implementation.

This implements GOV-ORG-004.

---

## ORG-BR-003 — Statutoryly Recognized Organizational Units

An organizational unit shall exist in the ERP only where it is recognized by
an approved statutory or authoritative reference.

The ERP shall not create a new statutory organizational unit merely
because an application workflow requires one.

---

# 4. Apex Organization

## ORG-BR-004 — Single Apex Organization

The NSS ERP shall recognize one statutorily established apex
organization as the highest organizational authority.

The apex organization:

* has no parent;
* is the root of the organizational hierarchy;
* provides statutory authority for subordinate organizations; and
* is unique within the production organizational hierarchy.

This implements GOV-ORG-001.

---

## ORG-BR-005 — No Organization Outside the Statutory Hierarchy

No organizational entity maintained by the ERP shall exist outside the
statutory organizational hierarchy.

All organizational entities shall derive their authority through the
statutory hierarchy originating from the apex organization.

---

## ORG-BR-006 — Single Organizational Root

The organizational hierarchy shall contain one and only one apex/root.

Multiple independent organizational trees representing the same statutory
organization are prohibited.

This implements GOV-DATA-002.

---

# 5. Organizational Identity

## ORG-BR-007 — Permanent Organization Identity

Every organizational unit shall possess a permanent system-generated
identifier.

The identifier shall:

* be unique;
* remain stable throughout the organization's lifecycle;
* never be reused;
* never be reassigned; and
* be referenced consistently across ERP modules.

This implements GOV-DATA-004.

---

## ORG-BR-008 — Identifier Immutability

Once assigned, an organization's permanent identifier shall not change during
ordinary organizational maintenance.

A name, address, status, or other metadata change shall not alter the
permanent organizational identifier.

---

## ORG-BR-009 — Identifier Non-Reuse

An organizational identifier belonging to an inactive, archived, or otherwise
historical organization shall never be assigned to another organization.

---

## ORG-BR-010 — Duplicate Organizational Identity Prohibited

The ERP shall not maintain two independent organization records representing
the same statutorily recognized organizational unit.

---

# 6. Organizational Hierarchy

## ORG-BR-011 — Exactly One Parent for Non-Apex Organizations

Every organizational unit shall maintain exactly one valid parent
organization unless it is statutorily designated as the apex.

This implements GOV-ORG-003 and GOV-DATA-001.

---

## ORG-BR-012 — Valid Parent

A parent organization must:

* exist;
* be a valid organizational entity;
* belong to the approved organizational hierarchy; and
* not create an invalid hierarchy.

---

## ORG-BR-013 — No Multiple Parents

An organization shall not simultaneously have more than one immediate
parent organization.

---

## ORG-BR-014 — No Circular Organizational Relationships

The ERP shall prohibit circular organizational relationships.

Invalid example:

```text
Organization A
      ↓
Organization B
      ↓
Organization C
      ↓
Organization A
```

---

## ORG-BR-015 — No Orphan Organizational Units

A non-apex organizational unit shall not exist without a valid parent.

A NULL parent is permitted only for the single apex organization.

---

## ORG-BR-016 — Complete Organizational Lineage

Every organizational unit shall be traceable through its parent-child
relationships to the apex organization.

This lineage shall remain unambiguous.

This implements GOV-DATA-003.

---

## ORG-BR-017 — Lineage Preservation

Organizational lineage shall remain traceable throughout the organization's
lifecycle.

Lifecycle changes shall not destroy the ability to determine the
organization's position within the hierarchy.

---

## ORG-BR-018 — Parent-Child Integrity Enforcement

Parent-child integrity shall be enforced through both:

```text
Database Constraints
+
Application Validation
```

Invalid parent references shall not be permitted.

This implements GOV-DATA-001.

---

# 7. Hierarchical Level

## ORG-BR-019 — Hierarchical Level Must Be Represented

The ERP shall maintain the hierarchical level of each organizational unit
as required by GOV-002.

GOV-002 explicitly identifies:

* parent organization;
* child organization;
* reporting lineage;
* hierarchical level; and
* organizational status

as organizational relationships/data that the ERP shall maintain. 

---

## ORG-BR-020 — Hierarchical Level Shall Follow Authoritative Structure

The hierarchical level of an organization shall be derived from the approved
statutory organizational structure.

The application shall not invent organizational levels.

---

## ORG-BR-021 — Hierarchical Level Is Not Automatically Organization Type

The concepts:

```text
Organization Type
        ≠
Hierarchical Level
```

shall not be treated as identical unless an authoritative source explicitly
establishes that relationship.

---

## ORG-BR-022 — Hierarchical Level Design Status

The current three-table Organization design does not yet explicitly define a
separate `organization_level_master`.

Therefore:

```text
Hierarchical Level
=
REQUIRED BUSINESS CONCEPT

Physical Representation
=
TO BE FINALISED
```

This is an intentional design boundary and shall not be silently resolved by
inventing a new table.

---

# 8. Organizational Relationships

## ORG-BR-023 — Statutory Relationship

Relationships between organizational units shall be governed by
statutory authority.

The ERP shall preserve:

* parent organization;
* child organization;
* reporting lineage;
* hierarchical level; and
* organizational status.

---

## ORG-BR-024 — No Unsupported Reporting Relationship

The ERP shall not create reporting relationships that are unsupported by
authoritative references.

---

## ORG-BR-025 — No Parallel Organizational Hierarchy

A module shall not create a separate hierarchy for the same organizations.

The common Organization hierarchy is authoritative.

---

## ORG-BR-026 — No Unauthorized Organizational Level

The ERP shall not introduce a new statutory organizational level merely
for software convenience.

A new level requires authoritative support and applicable governance approval.

---

# 9. Organizational Authority

## ORG-BR-027 — Authority Follows Statutory Hierarchy

Authority within the ERP shall follow the statutory organizational
hierarchy.

An organizational unit shall exercise only the authority granted by the
statutory governance framework.

---

## ORG-BR-028 — ERP Record Does Not Grant Authority

Creating an organization record does not itself grant statutory or
governance authority.

Authority derives from the applicable statutory and governance
framework.

---

## ORG-BR-029 — No Authority Beyond Statutory Scope

No organization may exercise authority beyond the scope granted by the
statutory framework.

---

# 10. Delegated Authority

## ORG-BR-030 — Delegated Authority

Administrative delegation may permit operational management of organizational
records.

Delegation shall not modify:

* statutory ownership;
* statutory reporting relationships;
* organizational hierarchy; or
* permanent organizational identity.

Delegated authority shall be auditable.

---

## ORG-BR-031 — Delegation Cannot Create Statutory Structure

Delegated administrative authority shall not be used to create a new
statutory organizational level or unsupported hierarchy.

---

## ORG-BR-032 — Delegation Cannot Transfer Statutory Ownership

Delegated access shall not be interpreted as authority to transfer
statutory organizational ownership.

---

# 11. Organizational Independence

## ORG-BR-033 — No Unauthorized Independence

An organizational unit shall not operate independently of the statutory
organizational hierarchy.

---

## ORG-BR-034 — Unauthorized Hierarchy Creation Prohibited

The ERP shall prohibit unauthorized hierarchy creation.

---

## ORG-BR-035 — Unauthorized Restructuring Prohibited

Organizational restructuring shall not be performed through ordinary
uncontrolled administrative editing.

Applicable governance approval is required.

---

## ORG-BR-036 — Duplicate Statutory Entities Prohibited

The ERP shall prohibit duplicate representations of statutorily
recognized organizational entities.

---

## ORG-BR-037 — Unsupported Governance Relationships Prohibited

The ERP shall prohibit governance relationships not supported by authoritative
references.

---

# 12. Organizational Lifecycle

## ORG-BR-038 — Controlled Organizational Lifecycle

Organizational units shall follow a controlled lifecycle.

GOV-002 identifies the following typical lifecycle states:

```text
PROPOSED
APPROVED
ACTIVE
INACTIVE
ARCHIVED
```

These are the current documented lifecycle states, but GOV-002 describes
them as "typical" states rather than defining a complete exhaustive
transition matrix.

---

## ORG-BR-039 — Governance-Controlled Lifecycle Transition

Lifecycle transitions shall occur only through approved governance
procedures.

The Organization Module shall not invent independent lifecycle transition
rules.

---

## ORG-BR-040 — Proposed Organization

A `PROPOSED` organization represents an organizational unit that has been
proposed but has not yet completed the applicable approval process.

A proposal shall not automatically receive operational authority.

---

## ORG-BR-041 — Approved Organization

An `APPROVED` organization represents an organizational unit that has received
the applicable organizational approval.

Approval does not automatically mean that the organization is operationally
active.

---

## ORG-BR-042 — Active Organization

An `ACTIVE` organization represents a currently operational organizational
unit within the approved hierarchy.

---

## ORG-BR-043 — Inactive Organization

An `INACTIVE` organization is not currently active but remains a valid
historical organizational identity.

Inactivation does not mean deletion.

---

## ORG-BR-044 — Archived Organization

An `ARCHIVED` organization remains preserved as historical organizational
information.

Archival does not authorize deletion or identifier reuse.

---

## ORG-BR-045 — No Automatic Inactivation

The ERP shall not automatically change an organization's status to
`INACTIVE` merely because of:

* low membership;
* no attendance;
* lack of recent activity;
* lack of recent transactions; or
* other operational metrics,

unless a separately approved governance rule establishes such behavior.

---

## ORG-BR-046 — No Automatic Archival

The ERP shall not automatically archive an organization based solely on
operational inactivity or elapsed time unless an approved governance rule
establishes such a mechanism.

---

## ORG-BR-047 — Lifecycle Does Not Replace Organizational Identity

A lifecycle status change shall not create a replacement organizational
identity.

---

# 13. Organizational Changes

## ORG-BR-048 — Organizational Change Requires Governance Control

Any change that affects the approved organizational governance model shall
follow the applicable Governance Change Control process.

---

## ORG-BR-049 — Parent Change Is a Structural Change

Changing an organization's parent is a structural organizational change.

It shall require the applicable governance authorization.

---

## ORG-BR-050 — Parent Change Preserves Identity

An approved parent change does not automatically create a new organization.

The existing permanent organizational identifier remains unchanged unless
the authoritative decision establishes a genuinely new organizational
entity.

---

## ORG-BR-051 — Parent Change Must Preserve Historical Traceability

Where an approved parent change occurs, historical traceability of the
previous relationship shall be preserved through the applicable audit/history
framework.

---

## ORG-BR-052 — Name Change Does Not Automatically Create New Organization

Changing an organization's approved name does not automatically create a new
organizational identity.

---

## ORG-BR-053 — Address Change Does Not Automatically Create New Organization

Changing an organization's address does not automatically create a new
organization.

---

# 14. Organization Type

## ORG-BR-054 — Organization Type Is Controlled

Organization type shall be represented through controlled organization-type
master data.

---

## ORG-BR-055 — Organization Type Values Require Authority

The ERP shall not treat arbitrary user-created organization types as
statutory organizational types.

The authoritative source must establish the valid organizational type
vocabulary.

---

## ORG-BR-056 — Type Does Not Automatically Determine Status

Organization type and lifecycle status are separate concepts.

```text
Organization Type
        ≠
Organization Status
```

---

## ORG-BR-057 — Type Does Not Automatically Determine Hierarchy

The ERP shall not assume that an organization type automatically determines
its parent or child relationship unless supported by the authoritative
organizational model.

---

# 15. Organization Status

## ORG-BR-058 — Controlled Organization Status

Organization status shall be represented through the controlled
`organization_status_master`.

---

## ORG-BR-059 — No Unsupported Status

The current solution shall not introduce additional statutory lifecycle
states without an approved governance change.

Examples such as:

```text
SUSPENDED
CLOSED
DISSOLVED
REJECTED
```

shall not be treated as current Organization lifecycle states unless
authoritatively approved.

---

# 16. Organizational Address

## ORG-BR-060 — Current Address Model

The current Organization v1 design permits one current organization address
represented directly on the organization entity.

---

## ORG-BR-061 — No Multiple Current Addresses

The current v1 design does not support multiple concurrent organization
addresses.

---

## ORG-BR-062 — No Separate Organization Address Entity

The current v1 Organization design does not include:

```text
organization_address
```

as a separate table.

---

## ORG-BR-063 — Common Location Masters

Where applicable, organization geographic information shall reuse the common
Location Master framework.

The Organization Module shall not create duplicate country, state, district,
or equivalent geographic masters.

---

## ORG-BR-064 — Administrative vs Physical Location

The project source distinguishes:

```text
ANCHALIKA = Administrative Unit
ZILLA     = Administrative Unit
SAKHA     = Physical Sangha Location
```

Therefore physical address requirements shall not automatically be inferred
from organizational type alone. 

---

# 17. Cross-Module Rules

## ORG-BR-065 — Organization Is the Common Organizational Authority

Where another ERP module references an organization, it shall use the
Organization Module's organizational identity.

---

## ORG-BR-066 — Specialized Modules Shall Not Duplicate Organization

Modules such as:

```text
Sevak
Mahila
Kumari
Kishori
Kishor
```

shall not create a second master representation of the same organization.

---

## ORG-BR-067 — Person Boundary

The Organization Module shall not own general Person identity.

Person identity belongs to the Person Module.

---

## ORG-BR-068 — Membership Boundary

The Organization Module shall not own membership lifecycle.

Membership owns membership identity and lifecycle.

---

## ORG-BR-069 — Governance Boundary

The Organization Module shall not own current governance positions,
office-bearer assignments, or governance terms.

Those belong to the Governance Module.

---

## ORG-BR-070 — Attendance Boundary

The Organization Module shall not own attendance records or attendance
rules.

---

## ORG-BR-071 — Organizational Scope

Organizational lineage shall be usable by:

* reports;
* workflows;
* permissions;
* governance processes; and
* other authorized organizational operations.

This directly implements GOV-DATA-003.

---

## ORG-BR-072 — No Module-Specific Hierarchy

A downstream module shall not create an alternative organization hierarchy
for access, reporting, participation, or workflow purposes.

---

# 18. Audit and Historical Preservation

## ORG-BR-073 — Organizational Change Audit

Organizational changes shall be auditable.

Relevant changes include, where applicable:

* creation;
* approval;
* activation;
* inactivation;
* archival;
* parent change;
* type change;
* status change;
* name change; and
* address change.

---

## ORG-BR-074 — Historical Preservation

Organizational history shall remain traceable.

Inactive and archived organizations shall not be physically removed merely
because they are no longer operational.

---

## ORG-BR-075 — Historical Identifier Preservation

Historical organizational records shall retain their original permanent
identifier.

---

# 19. Governance Change Control

## ORG-BR-076 — Formal Governance Change

Changes to the approved organizational governance model shall follow
GOV-005.

---

## ORG-BR-077 — Governance Decision Traceability

Where a governance decision changes organizational structure or rules, the
solution artifact shall maintain traceability to the approved governance
decision.

GDR-001 requires governance decisions to identify the decision, rationale,
approving authority, approval date, and affected artifacts.

---

## ORG-BR-078 — No Undocumented Governance Decisions

An undocumented governance decision shall not be treated as authoritative
for modifying the Organization Module.

---

## ORG-BR-079 — Governance Compliance

All organizational database design, APIs, UI, workflows, reports, and
administrative functions shall comply with GOV-002.

Any deviation requires formal governance approval through the applicable
change-control process.

---

# 20. Data Integrity

## ORG-BR-080 — Database and Application Enforcement

Critical organizational integrity rules shall be enforced through both
database-level controls and application validation.

---

## ORG-BR-081 — Invalid Parent Rejection

The system shall reject a parent relationship when it would create:

* an invalid reference;
* multiple parents;
* an orphan;
* a circular relationship; or
* an unauthorized hierarchy.

---

## ORG-BR-082 — Invalid Root Rejection

The system shall prevent creation of a second organizational root.

---

## ORG-BR-083 — Invalid Organizational Structure Rejection

The system shall reject organizational structures that are unsupported by
the authoritative organizational model.

---

# 21. Current Design Boundaries

## ORG-BR-084 — No Separate Hierarchy Table

The current Organization design represents parent-child hierarchy through
the organization entity.

No separate `organization_hierarchy` table is currently frozen.

---

## ORG-BR-085 — No Separate Address Table

The current Organization design represents the current organization address
directly on `organization`.

No separate `organization_address` table is currently frozen.

---

## ORG-BR-086 — Hierarchical Level Remains a Design Gap

GOV-002 requires hierarchical level to be maintained, but the current
three-table design does not yet explicitly specify its physical representation.

Therefore:

```text
Business Requirement:
FROZEN

Physical Representation:
OPEN / REQUIRES DESIGN DECISION
```

This must be resolved before the physical Organization schema is frozen.

---

# 22. Rules Explicitly Not Assumed

The following are intentionally NOT frozen by this document unless supported
by a later authoritative source or governance decision:

```text
Exact organization type master values
Exact type-to-type parent compatibility matrix
Exact hierarchical-level storage mechanism
Complete lifecycle transition matrix
Automatic status transitions
Automatic organizational closure rules
Multiple address history
Additional statutory organization levels
```

---

# 23. Final Frozen Organization Rules

The following rules are considered firmly established from GOV-002:

```text
✓ Single statutory apex

✓ Apex has no parent

✓ Every non-apex organization has exactly one parent

✓ No multiple parents

✓ No circular organizational references

✓ No orphan organizational units

✓ Single organizational root

✓ Complete lineage to apex

✓ Permanent organizational identity

✓ Unique organizational identifier

✓ Identifier remains stable

✓ Identifier is never reused

✓ Statutory authority takes precedence

✓ Only authoritative references establish organizational structure

✓ Unauthorized hierarchy creation is prohibited

✓ Unauthorized restructuring is prohibited

✓ Duplicate statutory entities are prohibited

✓ Parallel organizational hierarchies are prohibited

✓ Unsupported governance relationships are prohibited

✓ Authority follows statutory hierarchy

✓ Delegation cannot alter statutory ownership

✓ Delegation cannot alter statutory reporting relationships

✓ Delegated authority is auditable

✓ Organizational lifecycle is controlled

✓ Lifecycle transitions require approved governance procedures

✓ Organizational independence cannot be created by ERP metadata

✓ Organizational lineage must remain traceable

✓ Organizational changes require governance control

✓ Governance changes require traceability

✓ Organizational data must comply with GOV-002
```

---

# 24. Open Design Items

The following items remain explicitly open and shall not be silently
implemented as frozen rules:

| Item                                          | Status               |
| --------------------------------------------- | -------------------- |
| Exact organization type values                | OPEN                 |
| Hierarchical level physical representation    | OPEN                 |
| Type-to-type hierarchy matrix                 | OPEN                 |
| Complete lifecycle transition matrix          | OPEN                 |
| Automatic lifecycle transitions               | NOT FROZEN           |
| Address history                               | OUT OF CURRENT SCOPE |
| Multiple current addresses                    | OUT OF CURRENT SCOPE |
| Additional statutory organization levels | NOT AUTHORIZED       |

---

# 25. Traceability

| Rule Area                        | Source       |
| -------------------------------- | ------------ |
| Apex organization                | GOV-ORG-001  |
| Statutory authority         | GOV-ORG-002  |
| Hierarchy integrity              | GOV-ORG-003  |
| Authoritative references         | GOV-ORG-004  |
| Parent-child integrity           | GOV-DATA-001 |
| Single root                      | GOV-DATA-002 |
| Organizational lineage           | GOV-DATA-003 |
| Permanent identifier             | GOV-DATA-004 |
| Lifecycle                        | GOV-002 §7.3 |
| Delegated authority              | GOV-002 §7.4 |
| Independence restrictions        | GOV-002 §7.5 |
| Governance compliance            | GOV-002 §9   |
| Governance decision traceability | GDR-001      |
| Governance change control        | GOV-005      |

---

# 26. Implementation Boundary

This document defines logical business rules only.

It does not define:

```text
SQL
PostgreSQL DDL
Django Models
API Endpoints
UI Implementation
Database Triggers
Index Implementation
```

Those are downstream implementation artifacts.

---

# 27. Final Organization Principle

The Organization Module shall preserve the following invariant:

```text
                    ONE APEX
                       │
                       ▼
              BYE-LAW ROOT
                       │
              ┌────────┴────────┐
              ▼                 ▼
          Organization       Organization
              │
              ▼
          Organization
              │
              ▼
          Organization
```

Every organizational unit must remain:

```text
Statutoryly recognized
        +
Uniquely identified
        +
Attached to one valid parent
        +
Traceable to the apex
        +
Governance controlled
```

---

# 28. Status

```text
DOCUMENT STATUS:
DRAFT — GOVERNANCE ALIGNED

VERSION:
1.1.0
```

---

# End of Document
