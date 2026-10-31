# NSS ERP — Organization Business Rules

**Document ID:** SOL-ORG-004  
**Version:** 1.10.0  
**Status:** DRAFT — GOVERNANCE ALIGNED  
**Amendment:** §28 (v1.2.0) — Type-to-Type Parent Hierarchy frozen (ORG-BR-087–095): resolves
the previously-OPEN parent compatibility matrix per an explicit governance decision
(2026-09-25), including the Mahila Sangha two-tier-by-parent convention and the Paribarik
Asana sangha_sevi-proxy note.  
**Amendment:** §29/§30 (v1.4.0) — ORG-BR-098 (Sakha premises attribute), ORG-BR-099
(address prohibited for ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA), ORG-BR-100 (parent
organization instance auto-resolution), per governance decision (2026-09-26).  
**Amendment:** §31 (v1.5.0) — ORG-BR-101 (Kumari/Sevak Sangha creation authority extended to
NSS-wide administrators), ORG-BR-102 (parent-Sakha auto-selection/dropdown rules for scoped
Sakha admins), per governance decision (2026-09-26).  
**Amendment:** §32 (v1.6.0) — ORG-BR-103 (Sakha auto-select/lock pattern generalised to
member-attach creation/update flows: Sangha Sevi and user-membership creation), per
governance decision (2026-09-26).  
**Amendment:** §33 (v1.7.0) — ORG-BR-104 (KUMARI_SANGHA/SEVAK_SANGHA, and the future local
MAHILA_SANGHA, carry no organization_code/short_code of their own and inherit all location/contact
detail from the parent Sakha — a wing shares the Sakha's identity), per governance decision
(2026-09-27).  
**Amendment:** §34 (v1.8.0) — ORG-BR-105 (organization_code for non-wing creatable types is the
org-type id_sequence_master value, auto-generated on submit and shown as a non-consuming live
preview via GET /admin/organizations/next-code; organization_id is no longer minted by this flow;
resolves the ORG-BR-104 organization_id OPEN item), per governance decision (2026-09-27).  
**Amendment:** §30 (v1.9.0) — ORG-BR-099 narrowed: country_pk/state_pk/district_pk carved back
out of the address prohibition for ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA — these are
administrative jurisdiction, not a physical premises, and are now allowed/displayed for every
organization type; only premises-specific columns (address_line_1/2, city_village_pk,
postal_code_pk, latitude, longitude) remain prohibited for these three types, per governance
decision (2026-09-28).  
**Amendment:** §36 (v1.10.0) — ORG-BR-106..109 and notes on ORG-BR-087/088/095: Advisory Board as a 14th singleton organization type, immutable name, DB singleton trigger (generalised to KENDRA/NILACHALA_KUTIRA/SMRUTI_MANDIRA/ADVISORY_BOARD and the central Mahila Sangha), Sakha/Sakha Asana re-parenting approval chain (Kendra GB members and NSS_ERP_ADMIN exempt), per owner-directed decisions (2026-10-30) recorded as GDR-005, GDR-006, GDR-007.  
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

The frozen organization type list (8 types):

```text
KENDRA          = Central Body (unique — only one exists)
NILACHALA_KUTIRA = Spiritual Residence (unique)
SMRUTI_MANDIRA  = Memorial Temple (unique)
ANCHALIKA       = Administrative Unit (multiple instances)
ZILLA           = Administrative Unit (multiple instances)
SAKHA           = Physical Sangha Location (multiple instances)
SAKHA_ASANA     = Approved Sakha without own building (multiple instances)
PATHA_CHAKRA    = Study Circle (multiple instances)
```

Unique organizations (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA) receive
fixed business codes: KEN, NKT, SMR respectively. They do not use
sequence-generated identifiers.

Multiple-instance organizations use per-type ID sequences:

```text
ANCHALIKA    → prefix ANC (e.g. ANC1)
ZILLA        → prefix ZL  (e.g. ZL1)
SAKHA        → prefix SKH (e.g. SKH1)
SAKHA_ASANA  → prefix SA  (e.g. SA1)
PATHA_CHAKRA → prefix PC  (e.g. PC1)
```

Physical address requirements shall not automatically be inferred
from organizational type alone. Administrative units (ANCHALIKA, ZILLA)
need not have a physical building. SAKHA_ASANA is Kendra-approved but
operates from a member's residence until a permanent building is
established. 

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
Exact hierarchical-level storage mechanism
Complete lifecycle transition matrix
Automatic status transitions
Automatic organizational closure rules
Multiple address history
Additional statutory organization levels
```

Note: "Exact type-to-type parent compatibility matrix" is now FROZEN — see §28
(ORG-BR-087–095).

Note: "Exact organization type master values" is now FROZEN — see
ORG-BR-064 for the authoritative 8-type list.

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
| Type-to-type hierarchy matrix                 | FROZEN — §28          |
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

# 28. Type-to-Type Parent Hierarchy (Frozen)

This section resolves the "Exact type-to-type parent compatibility matrix" item that
§22/§24 previously left OPEN. It is now FROZEN, sourced from an explicit governance
decision (2026-09-25) rather than derived from prior sections.

## ORG-BR-087 — Apex-Level Peers Are Outside the Parent-Child Tree

`KENDRA`, `NILACHALA_KUTIRA`, and `SMRUTI_MANDIRA` are each unique (`parent_organization_pk
IS NULL`). `NILACHALA_KUTIRA` and `SMRUTI_MANDIRA` are not a parent to any organization, and
are never each other's parent or child.

This does not contradict the single-apex/single-root rules in §23: `KENDRA` is the sole apex
of the parent-child hierarchy tree. `NILACHALA_KUTIRA` and `SMRUTI_MANDIRA` are unique
standalone institutions recognized by the Bye-Law that do not participate in that tree at
all — consistent with ORG-BR-064's existing note that these two "don't participate in the
parent hierarchy."


> **Amendment (2026-10-30, owner-directed, GDR-005):** a fourth apex-level singleton exists: `ADVISORY_BOARD` — but unlike `NILACHALA_KUTIRA`/`SMRUTI_MANDIRA` it carries `parent_organization_pk = KENDRA` (ORG-BR-106).

## ORG-BR-088 — Kendra's Direct Children

`KENDRA` is a valid parent only for: `ANCHALIKA_SANGHA`, `ZILLA_SANGHA`, `PATHA_CHAKRA`,
`PARIBARIK_SANGHA`, and the single Kendra/Central instance of `MAHILA_SANGHA` (ORG-BR-091).


> **Amendment (2026-10-30, owner-directed, GDR-005):** `KENDRA` is additionally a valid parent for the singleton `ADVISORY_BOARD` organization (ORG-BR-106).

## ORG-BR-089 — Anchalika and Zilla Are Siblings, Never Nested

`ANCHALIKA_SANGHA` and `ZILLA_SANGHA` may only be parented by `KENDRA`. Neither may be the
parent of the other.

## ORG-BR-090 — Sakha-Level Parenting

`SAKHA_SANGHA` and `SAKHA_ASANA` may only be parented by `ANCHALIKA_SANGHA` or
`ZILLA_SANGHA`.

## ORG-BR-091 — Mahila Sangha: One Type, Two Tiers Distinguished by Parent

`MAHILA_SANGHA` is a single organization type used at two tiers of the hierarchy, per the
NSS Mahila Sangha Bye-Law's central/branch structure — no separate type code exists for
either tier:

```text
parent = KENDRA        → the Kendra / Central Mahila Sangha (exactly one such row)
parent = SAKHA_SANGHA   → a local, per-Sakha Mahila Sangha
```

> **Amendment (2026-10-31, owner-directed, GDR-008):** a local, per-Sakha Mahila Sangha may equally
> be parented by a `SAKHA_ASANA` (the shared Sakha-like set, `SAKHA_SANGHA` or `SAKHA_ASANA`). The
> `KENDRA` tier and its single-row singleton rule are unchanged.

The Bye-Law's central-body-supervises-branches relationship (the central Mahila Parichalana
Mandali overseeing branch Mahila Sanghas) is a **governance relationship**, not an
organizational-hierarchy parent-child relationship, and is deliberately **not** encoded via
`parent_organization_pk`. A local Mahila Sangha's org-tree parent is its own Sakha Sangha,
full stop — the central body's oversight is out of scope for this table's hierarchy column.

This tier distinction is an **implementation convention**, not a database-enforced rule:
no CHECK constraint requires "exactly one `MAHILA_SANGHA` row has `parent = KENDRA`" — that
is left to administrative discipline, matching this document's existing position (§10/§22)
that only the parent-*type* compatibility, not every finer-grained cardinality rule, is
frozen here.

## ORG-BR-092 — Kumari Sangha and Sevak Sangha Parenting

`KUMARI_SANGHA` and `SEVAK_SANGHA` may only be parented by `SAKHA_SANGHA`.

> **Amendment (2026-10-31, owner-directed, GDR-008):** `KUMARI_SANGHA` and `SEVAK_SANGHA` may be
> parented by `SAKHA_SANGHA` **or `SAKHA_ASANA`** (a Sakha Asana is a Sakha for all organizational
> purposes). ORG-BR-101/102 apply unchanged to an Asana as the parent Sakha: its own
> `NSS_ERP_SAKHA_ADMIN` may create them, and one active Kumari and one active Sevak per Sakha-like parent.

## ORG-BR-093 — Paribarik Sangha Parenting

`PARIBARIK_SANGHA` ("Paribarik Sangha", the family organisation attached to Kendra — Bye-Law
Preamble) may only be parented by `KENDRA`. It is an organization-level entity, not tied to
an individual `sangha_sevi` — contrast with ORG-BR-094.

## ORG-BR-094 — Paribarik Asana (Gruhasana) Attachment Is a Proxy, Not an Org Edge

`PARIBARIK_ASANA` ("Gruhasana") is conceptually attached to a `sangha_sevi` (a person's
membership record), not to another organization — that `sangha_sevi` in turn belongs to
exactly one `SAKHA_SANGHA`.

`nss.organization` has no column linking to `nss.sangha_sevi` today. Pending that design
(deferred to Membership/Parichaya Patra linkage work), `PARIBARIK_ASANA`'s
`parent_organization_pk` is set to the attached `sangha_sevi`'s current Sakha Sangha as an
**implementation proxy** — this is a technical workaround, not a frozen claim that
`PARIBARIK_ASANA` is truly "under" that Sakha Sangha org. `SAKHA_SANGHA` is the only
type-compatible parent allowed for `PARIBARIK_ASANA` regardless.

> **Amendment (2026-10-31, owner-directed, GDR-008):** `SAKHA_ASANA` is likewise a type-compatible
> parent (proxy for the attached `sangha_sevi`'s current Sakha, which may be an Asana — MBR-038A);
> the allowed parents are `SAKHA_SANGHA` or `SAKHA_ASANA`.

**Addendum (governance decision, 2026-09-26):** a `PARIBARIK_ASANA` organization's
existence tracks its attached `sangha_sevi`'s Parichaya Patra lifecycle. It comes into
being when that member's household/Gruhasana status is established alongside Parichaya
Patra issuance (MBR-014), and its own status follows that credential's status changes
rather than being independently created, activated, or archived through a separate
organizational lifecycle action.

**Addendum (SOL-ARCH-013 FC-DECISION-01, 2026-10-01):** since Gruhasana's lifecycle
already tracks the Parichaya Patra's lifecycle (addendum above), it inherits that
credential's Dola-Purnima-based `valid_from`/`valid_to` window as-is and needs no
independent validity calculation of its own.

## ORG-BR-095 — Admin-Scope Levels Reflect This Hierarchy

`nss.admin_scope`/`nss.role_master`'s `scope_level` enum (`NSS-WIDE`, `KENDRA`, `ANCHALIKA`,
`ZILLA`, `SAKHA`, `PATHA_CHAKRA`, `KENDRA_MAHILA_SANGHA`) is the set of organizational levels
that may hold a delegated administrative scope. It intentionally does not include
`SAKHA_ASANA`, `KUMARI_SANGHA`, `SEVAK_SANGHA`, `PARIBARIK_SANGHA`, or `PARIBARIK_ASANA` — no
role is scoped to those levels today. `KENDRA_MAHILA_SANGHA` refers to the single
`MAHILA_SANGHA` row whose parent is `KENDRA` (ORG-BR-091), not to `MAHILA_SANGHA` as a whole
— local, per-Sakha Mahila Sanghas fall under their own Sakha's `SAKHA` scope for
administrative purposes, not a distinct scope level of their own.


> **Amendment (2026-10-30, owner-directed, GDR-006):** the scope levels `KENDRA_MAHILA_SANGHA` and `ADVISORY_BOARD` carry no `organization_pk`; they resolve by organization type — `KENDRA_MAHILA_SANGHA` reaches every `MAHILA_SANGHA` organization (central and per-Sakha) plus subtrees, `ADVISORY_BOARD` reaches the Advisory Board organization. The earlier reading of `KENDRA_MAHILA_SANGHA` as "the single Kendra-parented row only" is superseded. Neither level is global (ADMIN-BR-076/077).

---

# 29. Organization Creation Authority (Frozen — governance decision, 2026-09-26)

## ORG-BR-096 — User-Creatable Organization Types

Through the standard Create Organization flow, only `ANCHALIKA_SANGHA`, `ZILLA_SANGHA`,
`PATHA_CHAKRA`, and `SAKHA_SANGHA` may be created directly by a user. Apex peers (`KENDRA`,
`NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`) are pre-existing singletons (ORG-BR-087) and are never
created. `SAKHA_ASANA` is a recognized bylaw type (ORG-BR-090) but is not offered as a
separate creation option: in current practice the term has fallen out of operational use —
once Kendra approves a new Sakha it is called `SAKHA_SANGHA` regardless of whether it has
yet secured permanent premises. A new Sakha is therefore created directly as
`SAKHA_SANGHA`; "no permanent premises yet" is a status/address attribute on that row, not a
distinct organization type a user selects.

**Type transition.** Where a `SAKHA_ASANA`-typed row exists (historical or seed data),
promotion to `SAKHA_SANGHA` on securing permanent premises is a same-row `organization_type`
change — identity-preserving, consistent with ORG-BR-052/ORG-BR-053's treatment of name and
address changes. It does not archive the row or create a new organization; all credentials,
affiliations, and the Local Sakha ERP Number sequence anchored to that organization carry
forward unchanged.

**Auto-created, not user-created.** The local wing body `MAHILA_SANGHA` whose parent is a
`SAKHA_SANGHA` (ORG-BR-091) is not created through this flow and is never independently
selectable in the Organization Type field. It is auto-created by the system as a direct
consequence of creating its parent `SAKHA_SANGHA`, governed by that same Sakha's leadership.
Creation is not itself membership-triggered, but affiliation is: the moment any female
member's Sakha affiliation is recorded, she is automatically also affiliated to that Sakha's
Mahila Sangha, which is understood as part of the Kendra Mahila Sangha (the non-hierarchical
wing-level relationship ORG-BR-091 already describes, distinct from `parent_organization_pk`).

**Optional, Sakha-gated creation.** Local `KUMARI_SANGHA` and `SEVAK_SANGHA` (ORG-BR-092) are
optional per Sakha — some Sakhas establish them, others do not — and are neither
auto-created nor available in the standard Create Organization dropdown. Creation authority
rests with that Sakha's own governing body: a user holding `NSS_ERP_SAKHA_ADMIN`, whose
`admin_scope.organization_pk` matches that specific Sakha, may create one for their own Sakha
only. This resolves the "org row vs. no org row" question raised by MBR-046: the local
Mahila/Kumari/Sevak Sangha organization genuinely exists once established, but a member's
affiliation to it never creates a separate identity — the org row is either auto-provisioned
infrastructure (Mahila Sangha) or a deliberate, narrowly-scoped Sakha decision (Kumari/Sevak
Sangha), never something an operator builds through the general flow.

## ORG-BR-097 — Paribarik Sangha Creation Is Restricted to Kendra Governing-Body Administrators

Creation of a `PARIBARIK_SANGHA` organization (parent `KENDRA`, ORG-BR-093) is disabled by
default in the Create Organization flow. It may be created only by a user holding the
`NSS_ERP_KENDRA_ADMIN` role.

---

## ORG-BR-098 — Sakha Premises Is an Attribute, Never a Distinct Stored Type

A `SAKHA_SANGHA` organization records whether it has secured its own permanent premises via a
dedicated `has_own_premises` boolean attribute on the organization row — never by storing a
different `organization_type`. Every Sakha created through the standard Create Organization
flow (ORG-BR-096) is typed `SAKHA_SANGHA` regardless of the premises answer given at creation.

"Sakha Asana" is a day-to-day operational label for a `SAKHA_SANGHA` row with
`has_own_premises = FALSE`. It is not a selectable creation option and the standard flow never
writes `organization_type = SAKHA_ASANA`. A Sakha lacking its own premises is, in every other
respect, indistinguishable from one that has them: it may hold members (MBR-038A), be
administered by a scoped Sakha admin (ORG-BR-095), and hold the same organizational authority.
This confirms, per governance decision (2026-09-26), that `has_own_premises` never gates
membership or admin-scope eligibility.

**Legacy note.** `SAKHA_ASANA` remains a valid `ORGANIZATION_TYPE` master-data value
(ORG-BR-090) for any pre-existing seed/historical rows typed that way before this rule. It is
not removed from the schema — only never written by the standard creation flow going forward.
Promotion of any such legacy row is the existing same-row `organization_type` change described
in ORG-BR-096.

---

## ORG-BR-100 — Parent Organization Instance Auto-Resolution

Where a creatable organization type (ORG-BR-096) has exactly one legal parent type
(ORG-BR-088–090) and exactly one existing instance of that parent type —
`ANCHALIKA_SANGHA`, `ZILLA_SANGHA`, and `PATHA_CHAKRA`, each parented only by the single
`KENDRA` row — the Create Organization flow shall resolve and lock that parent automatically;
the operator does not select it.

Where a legal parent type has more than one instance — `SAKHA_SANGHA`, parented by any
`ANCHALIKA_SANGHA` or `ZILLA_SANGHA` (ORG-BR-090) — the operator must select the specific
parent organization; no instance is inferred.

This rule concerns only which specific organization *row* is assigned as parent. It does not
alter ORG-BR-090's parent-type compatibility, and it does not extend to `KUMARI_SANGHA` /
`SEVAK_SANGHA` (ORG-BR-092): although their parent type is singular (`SAKHA_SANGHA`), that
type has many instances, so their Sakha-admin-gated creation path (ORG-BR-096) still requires
the creator to identify which Sakha explicitly — never auto-resolved.

---

# 30. Sakha Address vs Administrative-Unit Address (Frozen — governance decision, 2026-09-26; narrowed 2026-09-28)

## ORG-BR-099 — Physical Premises Address Prohibited for Non-Physical Organization Types

`SAKHA_SANGHA` represents a physical location and holds a physical address (ORG-BR-064).
`ANCHALIKA_SANGHA`, `ZILLA_SANGHA`, and `PATHA_CHAKRA` are purely administrative/organizational
units with no premises of their own. Per governance decision (2026-09-26), this is elevated
from ORG-BR-064's permissive reading ("need not have a physical building") to a hard
prohibition: an organization of type `ANCHALIKA_SANGHA`, `ZILLA_SANGHA`, or `PATHA_CHAKRA`
shall never carry a physical premises address. The premises-address columns on
`nss.organization` (`address_line_1`, `address_line_2`, `city_village_pk`, `postal_code_pk`,
`latitude`, `longitude`) must remain `NULL` for these three types, enforced at database level.

**Amendment (2026-09-28):** `country_pk`/`state_pk`/`district_pk` are carved back out of this
prohibition. These three types do correspond to a real administrative jurisdiction — which
state/district a given Anchalika Sangha, Zilla Sangha, or Patha Chakra covers — even though they
hold no premises of their own; conflating "has no building" with "cannot record which
state/district it administers" was too broad. Country/state/district are now allowed (and
displayed) for every organization type, including these three; only the premises-specific
columns above remain prohibited.

This does not apply to `KENDRA`, `NILACHALA_KUTIRA`, or `SMRUTI_MANDIRA` (unique apex
institutions, out of scope of this rule) nor to `SAKHA_SANGHA` (ORG-BR-064, ORG-BR-098).

**Deferred — OPEN, not decided.** Because `PATHA_CHAKRA` (and `ANCHALIKA_SANGHA`/`ZILLA_SANGHA`)
can never hold a premises address, any future requirement to display a full street
address/contact detail for one must source it from its current office-holder (e.g. its
president) at display time, not store it on the organization row — jurisdiction
(country/state/district) is now available directly on the row per the amendment above, but a
literal building address is not. This depends on Governance-module office-holder data not yet
linked to Organization and is explicitly deferred.

---

# 31. Kumari Sangha / Sevak Sangha Creation Authority and Parent-Sakha Selection (Frozen — governance decision, 2026-09-26)

## ORG-BR-101 — Kumari Sangha / Sevak Sangha Creation Authority Extended to NSS-Wide Administrators

ORG-BR-096 restricts local `KUMARI_SANGHA`/`SEVAK_SANGHA` creation to that Sakha's own
`NSS_ERP_SAKHA_ADMIN` (scoped to that specific Sakha). This is widened, not replaced: an
NSS-wide administrator (`NSS-WIDE` scope) may also create a `KUMARI_SANGHA` or `SEVAK_SANGHA`
for any active `SAKHA_SANGHA`. A `NSS_ERP_SAKHA_ADMIN` remains restricted to Sakhas covered by
their own `SAKHA`-level `admin_scope` — they may never create or update one for a Sakha outside
their scope.

## ORG-BR-102 — Parent-Sakha Selection for Kumari Sangha / Sevak Sangha

Applies uniformly to creation and update of `KUMARI_SANGHA`/`SEVAK_SANGHA` (any UI or API
surface offering a "select Sakha" step for these two types):

1. **NSS-wide administrator** — every active `SAKHA_SANGHA` is offered; no auto-selection.
2. **`NSS_ERP_SAKHA_ADMIN` scoped to exactly one Sakha** — that Sakha is auto-selected and
   locked; no dropdown needed.
3. **`NSS_ERP_SAKHA_ADMIN` scoped to more than one Sakha** — among their scoped Sakhas, if
   exactly one currently lacks an active organization of the type being created, that Sakha is
   auto-selected. If zero or more than one lack it, no auto-selection is made and all of the
   admin's scoped Sakhas are offered as a filtered dropdown for manual choice.

A Sakha-scoped admin is never offered, nor may select, a Sakha outside their own `admin_scope`
— enforced server-side, not merely hidden in the UI.

**Cardinality basis (derived, not independently specified).** "Lacks an organization of the
type being created" in point 3 presumes at most one active `KUMARI_SANGHA` and one active
`SEVAK_SANGHA` may exist per Sakha at a time — this is the natural reading of "the Sakha which
doesn't have this" and is enforced as a real constraint (partial unique index on
`parent_organization_pk` + `organization_type_master_data_pk`, scoped to these two types), not
just assumed at the API layer.

---

# 32. Sakha Auto-Select / Lock for Member-Attach Flows (Frozen — governance decision, 2026-09-26)

## ORG-BR-103 — Generalised Sakha Selection for Member-Attach Creation / Update

The parent-Sakha selection behaviour of ORG-BR-102 generalises to every creation/update flow
where an administrator attaches a member-scoped record to a `SAKHA_SANGHA` — currently Sangha
Sevi creation (`POST /admin/sangha-sevi`) and user creation with an inline membership
(`POST /admin/users` with `create_sangha_sevi = true`). The same UI/API contract applies:

1. **NSS-wide administrator** — every active `SAKHA_SANGHA` is offered; no auto-selection; a
   Sakha must be supplied (nothing to infer).
2. **Administrator scoped to exactly one Sakha** — that Sakha is auto-selected and the dropdown
   is locked; omitting the Sakha on submit is permitted and resolves to that Sakha server-side.
3. **Administrator scoped to more than one Sakha** — their own scoped Sakhas are offered; an
   explicit in-scope choice is required.

**Distinction from ORG-BR-102.** Member-attach flows carry **no one-per-Sakha cardinality** — a
Sakha holds many members — so the "auto-select the Sakha that lacks one" disambiguation of
ORG-BR-102 point 3 does **not** apply here; a multi-Sakha admin simply picks.

**Authorisation basis.** Eligibility is exact-match against the caller's `SAKHA`-level
`admin_scope` (plus every Sakha for an `NSS-WIDE` caller), consistent with
`UserContext.has_scope_for_org` — scope is **not** hierarchical. A scoped admin may never
attach to a Sakha outside their own scope; this is enforced server-side, not merely hidden in
the UI. The MBR-038A Sakha-only membership guard continues to apply on top of this selection.

**Scope of this amendment (stated explicitly, not silently widened).** ORG-BR-103 covers the two
member-attach flows named above. It deliberately does **not** restate authority for flows that
already have a distinct, governance-defined authority model — role-scope grants
(`POST /admin/users/{pk}/roles`), family self-service creation, public self-registration, and
membership-claim editing — which retain their existing rules and are out of scope for this rule.

---

# 33. Kumari Sangha / Sevak Sangha / Local Mahila Sangha Are Wings of a Sakha (Frozen — governance decision, 2026-09-27)

## ORG-BR-104 — Wing Organizations Carry No Code and Inherit Detail from the Parent Sakha

A local `KUMARI_SANGHA`, `SEVAK_SANGHA`, or the per-Sakha (local) `MAHILA_SANGHA` — the
`MAHILA_SANGHA` whose parent is a `SAKHA_SANGHA` (ORG-BR-091), **not** the single Kendra/Central
Mahila Sangha whose parent is `KENDRA` — is a wing of its Sakha, not an independently-identified
organization. It operates from the Sakha's premises and shares the Sakha's identity (consistent
with ORG-BR-092's Sakha-only parenting (SAKHA_SANGHA or SAKHA_ASANA — GDR-008 amendment) and the wing-membership-shares-the-Sakha's-IDs convention,
MBR-046). Accordingly, when such a wing is created:

1. **It carries no `organization_code` and no `short_code` of its own — both are `NULL`.** The
   parent Sakha Sangha already holds those identifiers; a wing does not mint a separate one. Any
   client-supplied code or short_code for these types is **ignored** (not rejected — simply not
   persisted). The nullable `organization_code` column and the partial unique index on
   `short_code` (`WHERE short_code IS NOT NULL`) both permit this.
2. **Location and contact detail are inherited wholesale from the parent Sakha** — `address_line_1`,
   `country_pk`, `state_pk`, `district_pk`, `city_village_pk`, `postal_code_pk`, `phone_number`,
   `mobile_number`, `org_email`, `org_website_url`, and `org_youtube_channel_url` are copied from
   the resolved parent Sakha row. Any client-supplied values for these fields are likewise ignored
   for these types (the server substitutes the parent's).
3. **`parent_organization_pk`** is still resolved/locked exactly as ORG-BR-101/102 specify for
   `KUMARI_SANGHA`/`SEVAK_SANGHA` (creation authority + Sakha selection). This rule governs only
   what identity/detail is copied from — or omitted relative to — that resolved parent.

**UI contract.** When the operator selects `KUMARI_SANGHA`/`SEVAK_SANGHA`, the Create Organization
form hides the code, short-code, address, location, and contact inputs and shows a "part of the
parent Sakha" notice; only the name, type, and parent-Sakha selection remain, and the frontend does
not send the hidden fields.

**Implementation scope (2026-09-27).** Points 1–3 are implemented for `KUMARI_SANGHA` and
`SEVAK_SANGHA` via `POST /admin/organizations`. The local `MAHILA_SANGHA` is **not yet creatable
through any API** (its `MAHILA_SANGHA` id-sequence is reserved for a future module); this rule is
stated now so that whenever local-Mahila creation is built it follows the same no-own-code,
inherit-from-Sakha contract. The previously-OPEN question — whether a wing should also forgo its own
`organization_id` — is now **resolved by ORG-BR-105**: `POST /admin/organizations` no longer mints an
`organization_id` for any type (the org-type sequence is materialised as `organization_code`
instead), so wings carry neither identifier. `organization_id` remains a nullable legacy column.

---

## ORG-BR-105 — Organization Code Is the Org-Type Sequence Value, Previewed Before Submit

For every **non-wing creatable** organization type (`ANCHALIKA_SANGHA`, `ZILLA_SANGHA`,
`PATHA_CHAKRA`, `SAKHA_SANGHA`), the `organization_code` is **auto-generated from that type's
`id_sequence_master` sequence** — it is not entered by the operator. The generated value is
`prefix + next counter value` (e.g. `SAKHA` → `SKH176`), matching the established data convention
where Sakha codes are `SKH1`, `SKH2`, … This is the visible "org code".

1. **The sequence is the single source.** The old count-of-existing-rows scheme
   (`<TYPE[:3]><count+1>`) is retired. `organization_code` is now `next_id(<type sequence>)`,
   minted atomically on submit — the only point the sequence is consumed.
2. **`organization_id` is not minted by this flow.** The org-type sequence value lands in
   `organization_code`; the legacy `organization_id` column is left `NULL`. This removes the prior
   dual-identifier redundancy (a separate sequence-based `organization_id` alongside a count-based
   `organization_code`).
3. **Live, non-consuming preview.** `GET /admin/organizations/next-code?organization_type_code=…`
   returns the code that *would* be minted next, computed as `prefix + (current_value + 1)` **without
   incrementing** the sequence. The Create Organization form calls it whenever a non-wing type is
   selected and shows the value in a read-only "Organization Code" field ("auto-generated — assigned
   on submit"). Because the preview only peeks, opening the form never burns a number; the real code
   is assigned solely on `POST /admin/organizations` and may differ from a stale preview if another
   org of the same type is created first. Wing types return `next_code = null` (ORG-BR-104 — no code).
4. **Explicit override retained for the API.** A client may still POST an explicit
   `organization_code`; it is honoured and uniqueness-checked. The standard UI does not send one.
5. **Counter integrity.** Because bulk-loaded organizations were inserted with their codes directly,
   without advancing `id_sequence_master`, the seed (`01_foundation/03_id_sequence_master.sql`)
   includes an idempotent, monotonic sync that raises each org-type counter to at least the highest
   existing code suffix of that type, so `next_id`/preview never collide with pre-existing codes.

**Scope.** Applies to the four standard creatable types. Wings (`KUMARI_SANGHA`/`SEVAK_SANGHA`,
future local `MAHILA_SANGHA`) carry no code at all (ORG-BR-104). Unique apex types (`KENDRA`,
`NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`) are singletons, not created through this flow.

---

# 36. Advisory Board Organization, and Sakha Re-Parenting Approval (owner-directed, 2026-10-30)

> Recorded as GDR-005, GDR-006, GDR-007 (status `Proposed` — NSS Governing Body ratification not verified).

## ORG-BR-106 — Advisory Board Is a Singleton Organization

`ADVISORY_BOARD` is the 14th organization type. Exactly one organization of this type exists
("Advisory Board", `organization_code` `ADB`, `short_code` `NSSAB`), parent `KENDRA`, seeded and
never user-created. It owns the Advisory Board's correspondence register. The Advisory Board
governance body stays NSS-wide (`organization_pk IS NULL`) and is not linked to it (GDR-005).

## ORG-BR-107 — Advisory Board Name Is Immutable

`organization_name` of an `ADVISORY_BOARD` organization cannot be changed by any actor
(including `NSS_ERP_ADMIN`); the attempt is refused with HTTP 422. Contact fields remain editable
by scope-allowed holders.

## ORG-BR-108 — Singleton Organizations Are Database-Enforced

Trigger `nss.fn_enforce_organization_singleton` (`08_organization_singleton_trigger.sql`)
refuses a second **active** organization for each singleton rule, on INSERT or on UPDATE OF
type / `is_active` / parent (checked only when a relevant column actually changed):

- type `KENDRA`, type `NILACHALA_KUTIRA`, type `SMRUTI_MANDIRA`, type `ADVISORY_BOARD`;
- the central (NSS/Kendra) Mahila Sangha: an active `MAHILA_SANGHA` whose parent is a
  `KENDRA`-type organization. Local per-Sakha Mahila Sanghas (parent = a Sakha) are
  unrestricted.

Owner amendment 2026-10-30 (GDR-005): originally only `ADVISORY_BOARD` was enforced
(`fn_enforce_advisory_board_singleton`, now dropped). `create_organization` and
`update_organization` mirror the rule with a clean 422 (`require_singleton_slot_free`). The
trigger never scans existing rows, so a database that already holds a duplicate still builds;
only new offending writes are refused.

## ORG-BR-109 — Sakha Re-Parenting Requires President-Chain Approval

Changing the parent of a `SAKHA_SANGHA` or `SAKHA_ASANA` (ORG-BR-090; the owner treats the
two as the same in current practice, and a Sakha Asana has its own Governing Body and President)
is applied directly only for a Kendra Governing Body member (holder of the §63 auto-granted
composite `NSS_ERP_KENDRA_ADMIN` scope) or the `NSS_ERP_ADMIN` super administrator (by role,
owner amendment 2026-10-30).
For every other actor — scoped admins, office bearers and a manually-assigned (non-Governing-Body)
Kendra Administrator — a request is filed and approved
by the Sakha President, then the leaving Anchalika/Zilla President, then the destination
Anchalika/Zilla President, then the Kendra President (owner amendment 2026-10-31); a step without a
seated President (or held by the requester) falls back to the Kendra President, and when the
Sakha's current parent is the Kendra there is no leaving step at all. The parent is unchanged until
the final approval (GDR-007).

> **Amendment (2026-10-31, owner-directed, GDR-007):** `SAKHA_ASANA` counts as a full Sakha for every
> Sakha-ness check (members MBR-038A, Advisory Board representation, attendance, correspondence,
> pickers, stats) via one shared definition per layer. This does **not** touch ORG-BR-096 (an Asana is
> never created through the standard flow), ORG-BR-098 (premises is an attribute of `SAKHA_SANGHA`),
> id-sequence/code generation. (The earlier carve-out for the wing parenting rules ORG-BR-091/092/094 is
> superseded by GDR-008 — see the amendment notes on those rules.)

---

# 35. Status

```text
DOCUMENT STATUS:
DRAFT — GOVERNANCE ALIGNED

VERSION:
1.8.0
```
