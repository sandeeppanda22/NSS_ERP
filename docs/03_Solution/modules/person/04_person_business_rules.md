# NSS ERP — Person Business Rules

**Document ID:** SOL-PER-003  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Person  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing Person identity within
the NSS ERP.

The Person Module is the foundational identity domain used by multiple
downstream modules.

The fundamental architectural principle is:

    Person ≠ Member

A Person may exist independently of NSS Membership.

---

# 2. Source and Authority

These rules shall be interpreted together with:

- NSS Bye-Law
- Approved governance standards
- Person solution documents
- Membership business rules
- Family business rules
- Common lifecycle rules
- Common audit/security standards

Where a higher-authority source conflicts with this document, the
higher-authority source prevails.

---

# 3. Rule Identification

Person rules use:

    PER-BR-001
    PER-BR-002
    PER-BR-003
    ...

---

# 4. Person Identity

## PER-BR-001 — Person Is an Individual Identity

A Person record represents one individual known to the NSS ERP.

The Person entity is the foundational identity record for that individual.

---

## PER-BR-002 — Person Is Independent of Membership

A Person may exist without NSS Membership.

The following are therefore valid:

    Person + Membership

and:

    Person without Membership

This is a frozen architectural principle.

---

## PER-BR-003 — Non-Member Persons Are Supported

The system shall support Persons who are not NSS Members.

Examples established in the project source include:

- Spouse of a Member
- Child of a Member
- Kumari participant
- Future applicant
- Historical Person

These Persons shall not be forced into Membership merely to obtain a Person
record.

---

## PER-BR-004 — Person Identity Is Not Derived From Membership

The system shall not create the Person identity only as a consequence of
Membership creation.

Person registration may occur before Membership.

---

# 5. Person Identity Identifier

## PER-BR-005 — Internal Person Primary Key

Every Person shall have a unique internal primary key:

    person_pk

The project standard uses UUID for internal primary keys.

---

## PER-BR-006 — Human-Readable Person ID

Every Person shall have a human-readable business identifier:

    person_id

Illustrative format:

    P00000001
    P00000002
    P00000003

---

## PER-BR-007 — Person ID Uniqueness

`person_id` shall be unique.

Two Person records shall never share the same Person ID.

---

## PER-BR-008 — Person ID Permanence

Once assigned, a Person ID shall remain associated with that Person.

---

## PER-BR-009 — Person ID Non-Reuse

A Person ID shall never be reassigned to another individual.

---

## PER-BR-010 — Centralized Person ID Generation

Person IDs shall be generated through the project's centralized ID sequence
mechanism.

The Person Module shall not maintain an independent ID counter.

---

## PER-BR-011 — No MAX + 1 Generation

The Person Module shall not generate identifiers using:

    MAX(person_id) + 1

or another application-local counter.

---

# 6. Person Identity vs Person Attributes

## PER-BR-012 — Attributes Do Not Define Identity

The following do not independently define Person identity:

- Name
- Mobile
- Email
- Address
- Date of Birth
- Gender
- Membership status

The permanent Person identity remains:

    person_pk
    +
    person_id

---

## PER-BR-013 — Name Change Preserves Identity

A correction or approved change to a person's name shall not create a new
Person.

---

## PER-BR-014 — Address Change Preserves Identity

A change of address shall not create a new Person.

---

## PER-BR-015 — Contact Change Preserves Identity

Changing mobile number or email shall not create a new Person.

---

# 7. Person Name

## PER-BR-016 — Core Name Fields

The Person record supports:

    first_name
    middle_name
    last_name

The exact handling of optional components follows the Person table design.

---

## PER-BR-017 — Name Correction

Authorized users may correct incorrect Person name information.

Corrections shall be auditable.

---

## PER-BR-018 — Duplicate Person From Name Variation Prohibited

A spelling variation, abbreviation, transliteration, or correction shall not
automatically result in a second Person record.

---

# 8. Gender

## PER-BR-019 — Gender Is Person Data

Gender, where recorded, belongs to the Person identity domain.

---

## PER-BR-020 — Controlled Gender Values

Where a gender master exists, Person records shall use the approved master
rather than arbitrary uncontrolled values.

---

## PER-BR-021 — Gender Does Not Determine Membership

Gender shall not itself determine whether a Person is an NSS Member.

Membership eligibility is governed by Membership rules.

---

# 9. Date of Birth

## PER-BR-022 — Date of Birth Belongs to Person

Date of birth is a Person-level attribute.

---

## PER-BR-023 — Person Creation and DOB

A Person may be created before all demographic information is available,
subject to the Person registration requirements.

---

## PER-BR-024 — Membership DOB Requirements

Where Membership approval requires date of birth, that requirement is owned
by Membership business rules.

The Person Module shall not duplicate Membership approval logic.

---

# 10. Date of Death

## PER-BR-025 — Death Is a Person-Level Lifecycle Event

A person's death is a global Person lifecycle event.

Where recorded, date of death belongs to the Person record.

---

## PER-BR-026 — Death Does Not Delete Person

A deceased Person shall remain historically identifiable.

Death shall not cause physical deletion of the Person identity.

---

## PER-BR-027 — Downstream Death Effects

Where downstream modules have lifecycle consequences arising from death,
those modules shall respond to the Person lifecycle event according to their
own approved rules.

The Person Module shall not independently rewrite downstream business
records.

---

# 11. Contact Information

## PER-BR-028 — Contact Method Requirement

A Person must have at least one contact method.

At least one of:

    mobile_number
    email

must be present.

Therefore:

    mobile_number IS NULL
    AND
    email IS NULL

is invalid.

---

## PER-BR-029 — Mobile Number May Be Null

Mobile number is not individually mandatory if a valid email address exists.

---

## PER-BR-030 — Mobile Number Uniqueness

When supplied, a mobile number shall be unique across Person records.

---

## PER-BR-031 — Email May Be Null

Email may be NULL when mobile number is present.

---

## PER-BR-032 — Email Is Not Globally Unique

Email is not required to be unique across Person records.

Multiple Persons may legitimately share an email address.

---

## PER-BR-033 — Contact Changes Are Auditable

Changes to mobile number or email shall be auditable.

---

# 12. Duplicate Person Prevention

## PER-BR-034 — Duplicate Identity Prevention

The system shall attempt to prevent creation of duplicate Person identities.

---

## PER-BR-035 — Duplicate Detection

Potential duplicate detection may consider approved identity attributes such
as:

- Mobile
- Name
- Date of Birth
- Email
- Family context

Duplicate detection is not equivalent to automatic identity merging.

---

## PER-BR-036 — Duplicate Detection Does Not Automatically Merge

The system shall not automatically merge two Person records merely because
they appear similar.

An authorized identity-management process is required.

---

# 13. Person Merge

## PER-BR-037 — Person Merge Is a Controlled Operation

If Person merging is supported, it shall be treated as a high-impact identity
operation.

---

## PER-BR-038 — Merge Must Preserve Relationships

A Person merge shall preserve, as applicable:

- Membership
- Family relationships
- Documents
- Governance history
- Attendance history
- Participation history
- Audit history

---

## PER-BR-039 — Merge Must Preserve Historical Traceability

A merge shall not destroy the ability to determine the historical identity
and relationships of the affected records.

---

# 14. Person and Membership

## PER-BR-040 — Membership Is Separate From Person

Membership is a separate domain entity.

The Person Module shall not store Membership as a replacement for Person
identity.

---

## PER-BR-041 — Existing Person Becomes Member

When an existing Person becomes an NSS Member:

    Existing Person
          ↓
    Membership Process
          ↓
    Membership Created

A second Person record shall not be created.

---

## PER-BR-042 — Sangha Sevi ID Belongs to Membership

Sangha Sevi ID belongs to the Membership domain.

It shall not replace:

    person_id

---

## PER-BR-043 — Person Without Sangha Sevi ID

A valid Person may have no Sangha Sevi ID.

---

## PER-BR-044 — Membership Does Not Own Person Identity

Membership references the Person identity.

Membership lifecycle changes do not destroy Person identity.

---

# 15. Person and Family

## PER-BR-045 — Family References Person

Family relationships shall reference existing Person identities.

---

## PER-BR-046 — Non-Member Family Members

A family member does not need to be an NSS Member in order to exist as a
Person.

---

## PER-BR-047 — Family Relationship Does Not Create Duplicate Person

If an existing Person is added to a family, the system shall reference the
existing Person rather than create another Person.

---

# 16. Person and Organization

## PER-BR-048 — Person and Organization Are Separate Entities

Person identity and Organization identity are independent.

    Person
       ≠
    Organization

---

## PER-BR-049 — Organization Association Does Not Create Person Duplicate

A Person moving between or participating in different organizational units
shall retain the same Person identity.

---

## PER-BR-050 — Organization Does Not Own Person Identity

An Organization shall not create a local duplicate Person master.

---

# 17. Person and Attendance

## PER-BR-051 — Attendance May Reference Person

Where applicable, Attendance shall reference the Person identity.

---

## PER-BR-052 — Attendance Does Not Create Person Identity

Attendance marking shall not create a duplicate Person simply because the
Person is not already represented in another domain.

The applicable Attendance workflow shall determine how unknown participants
are handled.

---

# 18. Person and Specialized Modules

## PER-BR-053 — Shared Person Identity

Specialized modules shall reuse the common Person identity.

This applies to:

- Mahila
- Kumari
- Kishori
- Kishor
- Sevak

where those modules require individual identity.

---

## PER-BR-054 — No Specialized Person Masters

Specialized modules shall not create separate general-purpose Person master
records for the same individual.

---

## PER-BR-055 — Same Person Across Modules

The same individual shall continue to use the same:

    person_pk

across applicable modules.

---

# 19. Person and Governance

## PER-BR-056 — Governance References Person

Governance assignments ultimately relate to Person identity.

---

## PER-BR-057 — Governance Does Not Own Person Identity

Governance shall not create a second Person identity for an office-bearer.

---

# 20. Person and Authentication

## PER-BR-058 — Person Does Not Automatically Create Login Account

Creating a Person does not automatically create a system login account.

---

## PER-BR-059 — Authentication Is Separate

Authentication owns:

- Login credentials
- Authentication state
- Access permissions

Person owns individual identity.

---

# 21. Documents

## PER-BR-060 — Person Documents

A Person may have zero or many associated documents.

---

## PER-BR-061 — Document Does Not Create Person

Uploading or registering a document shall not automatically create another
Person if the Person already exists.

---

## PER-BR-062 — Document Ownership

Document metadata and storage are separate from Person identity.

---

## PER-BR-063 — Document Access

Person-related documents shall be protected by the common authorization and
security framework.

---

# 22. Person Address

## PER-BR-064 — Person Address Belongs to Person Domain

Person address information is maintained as part of the Person domain.

---

## PER-BR-065 — Address Change Does Not Create Person

A Person moving to a new address remains the same Person.

---

## PER-BR-066 — Organization Address Is Separate

Person address shall not be confused with Organization address.

---

# 23. Person Lifecycle

## PER-BR-067 — Person Lifecycle Is Independent

Person lifecycle is independent of:

- Membership lifecycle
- Organization lifecycle
- Attendance lifecycle
- Governance lifecycle
- Specialized participation lifecycle

---

## PER-BR-068 — Membership Cessation Does Not Delete Person

When a person's Membership ends, the Person record remains.

---

## PER-BR-069 — Inactive Person

If a Person-level operational status is used, it shall not be confused with
Membership Status.

---

## PER-BR-070 — Historical Person Preservation

Historical Person records shall remain identifiable where required for
historical, governance, family, membership, or reporting purposes.

---

# 24. Soft Delete and History

## PER-BR-071 — Physical Deletion Prohibited for Historical Identity

A Person shall not be physically deleted merely because the person is no
longer active.

---

## PER-BR-072 — Soft Delete

Where record-management deletion is required, the common project soft-delete
standard shall apply.

---

## PER-BR-073 — Historical Relationships Preserved

Soft deletion or inactivation shall not destroy historical relationships.

---

# 25. Audit

## PER-BR-074 — Person Creation Is Audited

Creation of a Person shall be auditable.

---

## PER-BR-075 — Person Changes Are Audited

Material changes to Person information shall be auditable.

Examples:

- Name
- Mobile
- Email
- Date of Birth
- Date of Death
- Status
- Documents
- Identity corrections

---

## PER-BR-076 — Identity Operations Are Audited

High-impact operations such as duplicate resolution and Person merge shall
be fully audited.

---

# 26. ID and Database Integrity

## PER-BR-077 — Internal PK References

Foreign-key relationships shall reference the internal:

    person_pk

rather than the human-readable:

    person_id

This follows the project's database standard.

---

## PER-BR-078 — UUID Internal Identity

Internal Person primary key uses UUID according to the project database
standard.

---

## PER-BR-079 — Business ID Is Not Foreign-Key Identity

`person_id` is a business identifier and shall not replace `person_pk` as the
normal relational foreign key.

---

# 27. Security

## PER-BR-080 — Person Data Requires Authorization

Person information shall only be accessible according to the common
authentication and RBAC framework.

---

## PER-BR-081 — Sensitive Data Protection

Sensitive identity information shall not be unnecessarily exposed through:

- UI
- API
- Reports
- URLs
- Logs
- Search results

---

## PER-BR-082 — No Independent Person Security Model

The Person Module shall use the project's common security architecture.

It shall not create a separate permission framework.

---

# 28. Person and Organizational Scope

## PER-BR-083 — Scope Is Not Identity

A user's organizational scope does not change Person identity.

---

## PER-BR-084 — Person Can Have Cross-Organizational History

A Person may have historical relationships with more than one organizational
unit without becoming multiple Persons.

---

# 29. Data Quality

## PER-BR-085 — Core Identity Accuracy

Person records should contain accurate identity information to the extent
known and authorized.

---

## PER-BR-086 — Corrections Are Controlled

Corrections to Person identity data shall be performed by authorized users
and audited.

---

## PER-BR-087 — Missing Information

Missing non-mandatory Person information shall not be replaced with fabricated
or placeholder identity data.

---

# 30. Person Registration

## PER-BR-088 — Person Registration Is Independent Process

Person registration is an identity process.

It is not equivalent to:

- Membership enrollment
- Family enrollment
- Login registration
- Governance appointment

---

## PER-BR-089 — Person Registration May Precede Membership

A Person may be registered before Membership application or approval.

---

# 31. Membership Conversion

## PER-BR-090 — Existing Person Reuse

If an existing Person subsequently becomes a Member, the existing Person
record must be reused.

---

## PER-BR-091 — No Duplicate Person on Membership Approval

Membership approval shall not create a second Person record.

---

# 32. Family Conversion

## PER-BR-092 — Existing Person Reuse in Family

If an existing Person is added to a family relationship, the existing Person
record shall be reused.

---

# 33. Youth and Participant Conversion

## PER-BR-093 — Existing Person Reuse for Youth

A Kumari, Kishori, or Kishor participant who later becomes an NSS Member
shall retain the same Person identity.

---

## PER-BR-094 — Existing Person Reuse for Sevak

A Person becoming a Sevak shall retain the existing Person identity.

Sevak participation does not create another Person.

---

# 34. Historical Identity

## PER-BR-095 — Identity Never Recreated for History

Historical records shall reference the original Person identity wherever
possible.

---

## PER-BR-096 — Identity Survives Attribute Changes

A Person remains the same Person despite approved changes to:

- Name
- Address
- Contact details
- Membership status
- Organizational association

---

# 35. Person Module Ownership

## PER-BR-097 — Person Module Owns Identity

The Person Module owns:

- Person identity
- Person ID
- Core demographic information
- Core contact information
- Person-level record state
- Person document association
- Person identity audit context

---

## PER-BR-098 — Person Module Does Not Own Membership

Membership owns:

- Membership identity
- Sangha Sevi ID
- Membership type
- Membership status
- Membership lifecycle

---

## PER-BR-099 — Person Module Does Not Own Organization

Organization owns:

- Organization identity
- Organization hierarchy
- Organization lifecycle

---

## PER-BR-100 — Person Module Does Not Own Family

Family owns:

- Family identity
- Family relationships
- Family transitions

---

## PER-BR-101 — Person Module Does Not Own Governance

Governance owns:

- Governing bodies
- Positions
- Office-bearer assignments
- Terms
- Governance processes

---

# 36. Cross-Module Identity Rule

## PER-BR-102 — One Individual, One Person Identity

The ERP shall maintain one Person identity for one individual.

Domain-specific records shall reference that Person identity.

Conceptually:

    One Individual
          ↓
    One Person
          ↓
    Multiple Domain Relationships

---

# 37. Person Identity Invariant

## PER-BR-103 — Identity Invariant

The following invariant shall remain true:

    person_pk
          +
    person_id
          =
    one Person identity

Domain relationships may change without changing the underlying Person
identity.

---

# 38. Prohibited Patterns

## PER-BR-104 — No Member-as-Person Master

The Membership table shall not become the general Person master.

---

## PER-BR-105 — No Family-as-Person Master

The Family module shall not become the general Person master.

---

## PER-BR-106 — No Specialized Person Masters

Mahila, Kumari, Kishori, Kishor, Sevak, or other modules shall not create
duplicate general-purpose Person masters.

---

## PER-BR-107 — No Person Identity From Business Activity

Attendance, event participation, document upload, or another business event
shall not silently create duplicate Person identities.

---

# 39. Final Frozen Person Principles

The following principles are established by the current project source and
Person design:

```text
✓ Person ≠ Member

✓ Non-member Persons may exist

✓ Person may exist without Membership ID

✓ Person may exist without Parichaya Patra

✓ Person may exist without Anumati Patra

✓ Person may exist without Login Account

✓ Person is the foundational individual identity

✓ One individual should have one Person identity

✓ Person uses internal UUID primary key

✓ Person has human-readable Person ID

✓ Person ID is unique

✓ Person ID is permanent

✓ Person ID is never reused

✓ Person ID is centrally generated

✓ Foreign keys use person_pk

✓ Mobile is unique when supplied

✓ Email is not globally unique

✓ At least one contact method is required

✓ Membership is separate from Person

✓ Sangha Sevi ID belongs to Membership

✓ Family references Person

✓ Governance references Person

✓ Attendance may reference Person

✓ Specialized modules reuse Person identity

✓ Person survives Membership cessation

✓ Person survives organizational changes

✓ Historical Person identity is preserved

✓ Person changes are auditable

✓ Identity merge is controlled

✓ Person does not own Organization hierarchy

✓ Person does not own Membership lifecycle

✓ Person does not own Family relationships

✓ Person does not own Governance assignments

✓ Person does not own Attendance rules

✓ Person does not own Authentication
```

---

# 40. Explicitly Not Frozen Here

The following are intentionally left to later solution/implementation
documents:

```text
Exact Person address table structure

Exact document metadata structure

Exact Person status vocabulary

Exact sensitive-identity storage implementation

Exact duplicate-scoring algorithm

Exact Person merge workflow

Exact PostgreSQL CHECK constraints

Exact indexes

Exact API behavior

Exact UI workflows
```

These shall not be invented merely to complete this business-rules document.

---

# 41. Traceability

| Rule Area               | Source / Related Domain           |
| ----------------------- | --------------------------------- |
| Person ≠ Member         | Person architecture baseline      |
| Non-member Persons      | Person architecture baseline      |
| Person ID               | Foundation / ID sequence standard |
| UUID PK                 | Database standard                 |
| PK-based FKs            | Database standard                 |
| Mobile uniqueness       | Person business-rule baseline     |
| Email non-uniqueness    | Person business-rule baseline     |
| Contact requirement     | Person business-rule baseline     |
| Membership boundary     | Membership Module                 |
| Family boundary         | Family Module                     |
| Governance boundary     | Governance Module                 |
| Historical preservation | Common audit/lifecycle standard   |
| Security                | Common Security/RBAC standard     |

---

# 42. Final Person Business Rule

The Person Module shall preserve the following architectural model:

```text
                PERSON
                   │
   ┌───────────────┼────────────────┐
   │               │                │
   ▼               ▼                ▼
Membership       Family        Participation
   │                                │
   │                    ┌───────────┼───────────┐
   │                    ▼           ▼           ▼
   │                 Mahila      Kumari      Sevak
   │
   ▼
Sangha Sevi ID
```

The individual identity remains centralized in Person.

---

# 43. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
