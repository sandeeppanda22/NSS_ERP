# NSS ERP — Person Module Design

**Document ID:** SOL-PER-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Person
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Person Module provides the foundational identity record for every
individual known to the NSS ERP.

The module establishes the distinction between:

    Person
        ≠
    Member

A Person may exist in the ERP without being an NSS member.

The Person Module therefore forms an identity foundation for:

- Membership
- Family
- Governance
- Attendance
- Mahila
- Kumari
- Kishori
- Kishor
- Sevak
- Applications
- Documents
- Future modules

---

# 2. Core Principle

The fundamental Person Module principle is:

    One Person
        ↓
    One Person Identity
        ↓
    Zero or One NSS Membership
        ↓
    Potentially Many Domain Relationships

A person does not need to become an NSS member merely to exist in the ERP.

---

# 3. Person Is Not Membership

The following concepts are deliberately separate:

    Person
        =
    Individual Identity

    Membership
        =
    NSS Membership Relationship

Therefore:

    Person ≠ Member

A person may exist without:

- Membership ID
- Parichaya Patra
- Anumati Patra
- Login Account

This principle is explicitly established in the project source.

---

# 4. Person Examples

The Person Module may contain:

### NSS Members

A person who has an active or historical NSS membership.

### Family Members

A spouse, parent, child, or other family relationship who may not be an
NSS member.

### Kumari Participants

A person participating in Kumari-related activities who may not yet have
NSS membership.

### Kishor/Kishori Participants

Youth participants who may exist independently from regular NSS
membership.

### Future Applicants

A person who has entered an application or prospective-member process but
has not yet become a member.

### Historical Persons

A person who must remain represented for historical or organizational
records.

---

# 5. Person Identity

Each Person shall have a permanent internal identity.

The project database standard uses:

    person_pk UUID

as the internal primary key.

A separate human-readable:

    person_id

is maintained as the Person business identifier.

---

# 6. Person Primary Key

`person_pk` is the internal database identity.

It shall:

- be unique;
- be immutable;
- be used by foreign-key relationships;
- not be exposed as the normal human-facing identifier.

---

# 7. Person Business Identifier

`person_id` is the human-readable Person identifier.

The project source establishes human-readable business IDs such as:

    P00000001
    P00000002
    P00000003

The identifier is generated through the project's centralized ID-sequence
mechanism rather than application-specific hard-coded counters.

---

# 8. Person Identifier Permanence

Once assigned, a Person ID shall remain associated with that Person.

The identifier shall not be reassigned to another person.

---

# 9. Person Identity vs Name

A person's name is an attribute of the Person.

It is not the person's identity.

Therefore:

    person_pk
        +
    person_id

identify the person independently of:

- Name changes
- Spelling corrections
- Address changes
- Membership changes
- Family changes

---

# 10. Person Name

The Person record shall support:

- First name
- Middle name
- Last name

The exact naming implementation shall follow the project's naming
conventions.

---

# 11. Gender

Gender is maintained as a Person attribute.

Where the project uses controlled master data, gender values shall come from
the common master-data framework rather than arbitrary application text.

---

# 12. Date of Birth

Date of birth is a Person-level attribute.

A person may exist before complete demographic information is available.

Membership-specific requirements for date of birth belong to the Membership
Module.

---

# 13. Date of Death

The Person identity may retain a date of death when known.

Death does not mean that the Person record should be physically deleted.

Historical identity must remain available where required.

---

# 14. Person Lifecycle

Person lifecycle and Membership lifecycle are separate.

A person may remain in the Person Module even when:

- membership expires;
- membership becomes inactive;
- membership ends;
- the person has never been a member.

---

# 15. Person Deletion Principle

The Person Module shall not physically delete a Person merely because the
person is no longer operationally active.

Historical identity must be preserved where required by the project.

---

# 16. Person Contact Information

The Person Module supports contact information such as:

- Mobile number
- Email address

The current project business rule establishes:

- mobile number is unique;
- email is not required to be unique;
- at least one contact method is required.

---

# 17. Mobile Number

Mobile number is the preferred unique contact identifier where supplied.

Rules:

- Mobile number may be NULL.
- If supplied, it must be unique.
- The same mobile number cannot belong to multiple Person records.

---

# 18. Email Address

Email address may be NULL.

Email is not required to be globally unique.

Therefore multiple Person records may share an email address where the
business situation legitimately requires it.

---

# 19. Contact Method Requirement

A Person cannot be created without any contact method.

At least one of:

    mobile_number
    email

must be present.

Therefore:

    mobile_number IS NULL
        AND
    email IS NULL

is not permitted.

This rule is enforced at the Person data level.

---

# 20. Person Without Membership

A Person may exist without:

    sangha_sevi_id

This is a deliberate design decision.

Examples include:

- spouse of a member;
- child of a member;
- prospective member;
- Kumari participant;
- historical person.

---

# 21. Person to Membership Relationship

The Person Module does not own membership.

The logical relationship is:

    PERSON
       1
       |
       | 0..1 current membership
       |
       ▼
    MEMBERSHIP

Membership owns the membership lifecycle.

---

# 22. One Person — Membership Identity

The project architecture establishes the principle:

    One Person
        ↓
    One Membership
        ↓
    One Sangha Sevi ID

where a person becomes an NSS member.

The Person identity remains separate from the Sangha Sevi identity.

---

# 23. Sangha Sevi ID Boundary

`Sangha Sevi ID` belongs to the Membership domain.

It shall not replace:

    person_id

The distinction is:

    person_id
        =
    Person identity

    sangha_sevi_id
        =
    NSS membership identity

---

# 24. Family Relationship

Person is the foundational identity used by the Family Module.

Family relationships reference Person identities.

Examples:

    Person A
       |
       └── spouse → Person B

    Person A
       |
       └── child → Person C

Neither Person B nor Person C must necessarily be an NSS member.

---

# 25. Person and Organization

Person identity is independent of Organization identity.

The Organization Module owns:

    organization_pk
    organization_id

The Person Module owns:

    person_pk
    person_id

A Person may participate in organizational processes without becoming an
Organization record.

---

# 26. Person and Attendance

Attendance records should identify the person participating in attendance.

Attendance is not limited to membership identity where the applicable
attendance rules permit participation by non-members.

The exact attendance eligibility rules belong to the Attendance Module.

---

# 27. Person and Mahila

Mahila-specific participation may reference Person identity.

Mahila does not create a duplicate Person master.

---

# 28. Person and Kumari

Kumari participation may reference Person identity.

Kumari does not create a duplicate Person master.

---

# 29. Person and Kishor/Kishori

Kishor/Kishori participation may reference Person identity.

The youth modules do not create a second general-purpose Person identity.

---

# 30. Person and Sevak

Sevak participation references Person identity and, where applicable,
Membership identity.

Sevak does not create a separate general Person master.

---

# 31. Person and Governance

Governance participants and office-bearers ultimately relate to Person
identity.

Governance-specific assignment belongs to the Governance Module.

---

# 32. Person and Authentication

A Person does not automatically receive a login account.

Authentication is a separate domain.

Therefore:

    Person
       ≠
    User Account

A person may exist without system access.

---

# 33. Person and Documents

Person-related documents are associated with the Person identity.

The project source identifies:

    document_master

as part of the Person/identity foundation.

Document storage and document lifecycle are separate from Person identity.

---

# 34. Person Photo

A Person may have a photo associated with the identity record.

The earlier schema review identifies photo information as part of the
Person data model.

The final physical storage mechanism shall follow the project's Document
Management/storage architecture rather than embedding binary image data
directly in the Person identity table.

---

# 35. Sensitive Identity Information

Identity information must be handled according to the project's security
and privacy standards.

Sensitive identifiers shall not be exposed unnecessarily through:

- URLs
- Search results
- Logs
- Reports
- APIs
- UI

---

# 36. Aadhaar / Government Identity

The earlier Person schema discussion included:

- encrypted Aadhaar value;
- Aadhaar hash;
- Aadhaar last four digits.

Where such identity information is implemented, the final implementation
must follow the project's security requirements.

The Person Module shall not expose full sensitive identity values in normal
UI/reporting.

---

# 37. Address

A Person may have address information.

The Person address model shall remain distinct from:

    Organization Address

and:

    Family Address

where those concepts are separately represented.

---

# 38. Multiple Person Addresses

The project source indicates that multiple addresses may be supported for a
Person.

The exact physical address-table structure shall be finalized in the Person
ERD/Table Design documents.

This design document does not invent an additional table prematurely.

---

# 39. Person Search Identity

Person search should be capable of locating a Person using appropriate
identity/contact attributes such as:

- Person ID
- Name
- Mobile number
- Email

Search must respect authorization and sensitive-data rules.

---

# 40. Duplicate Person Prevention

The system should detect probable duplicate Person records.

Potential duplicate indicators include:

- Same mobile number
- Similar name
- Same date of birth
- Matching family context
- Other approved identity attributes

Duplicate detection must not automatically merge records without an
authorized process.

---

# 41. Person Merge Boundary

A Person merge, if required, is a high-impact identity operation.

It must preserve:

- historical relationships;
- membership references;
- family relationships;
- documents;
- participation records;
- audit history.

No automatic destructive merge is permitted.

---

# 42. Person Identity Corrections

Authorized users may correct Person demographic/contact information subject
to the project's audit requirements.

Corrections must not create a second Person merely because an attribute was
incorrect.

---

# 43. Person Lifecycle and Historical Records

Historical records shall continue to reference the same Person identity.

A correction to:

    Name
    Mobile
    Email
    Address
    Other Person Data

does not automatically create a new Person.

---

# 44. Person and Membership Approval

Person-level data may be incomplete when the Person is first registered.

Membership approval may impose additional mandatory information.

Those requirements belong to Membership business rules.

---

# 45. Person Registration vs Membership Application

The following are distinct:

    Person Registration
        ↓
    Person exists

and:

    Membership Application
        ↓
    Membership process

A person may enter the Person Module before entering the Membership Module.

---

# 46. Person Status

The Person Module may require an operational active/inactive state for
record-management purposes.

Such a Person status must not be confused with:

    Membership Status

or:

    Organization Status.

---

# 47. Person Status Separation

The concepts remain separate:

    Person Status
        ≠
    Membership Status
        ≠
    Organization Status

A person's membership may become inactive without deleting the Person.

---

# 48. Person History

The Person identity shall support historical traceability.

Where important Person attributes change, the common audit/history framework
shall preserve appropriate evidence.

---

# 49. Audit

Person operations shall be auditable.

Relevant operations include:

- Person creation
- Person update
- Contact change
- Identity correction
- Status change
- Document association
- Authorized merge/correction
- Sensitive-data access where required

---

# 50. Soft Delete

The project-wide audit standard supports soft deletion rather than ordinary
physical deletion for major transactional records.

The Person Module shall follow the common project soft-delete/audit standard.

The exact physical implementation belongs to the database design.

---

# 51. Person ID Generation

Person IDs shall use the centralized ID sequence mechanism.

The project source explicitly recommends centralized sequence management to
avoid application-specific ID generation and duplicate IDs.

---

# 52. Person ID Example

Illustrative format:

    P00000001
    P00000002
    P00000003

The exact prefix/padding configuration belongs to the Foundation
`id_sequence_master`.

---

# 53. No Hard-Coded ID Generation

The Person Module shall not independently calculate:

    MAX(person_id) + 1

or use another application-only counter.

ID generation must use the centralized sequence mechanism.

---

# 54. Person Module Ownership

The Person Module owns:

```text
Person Identity
Person Business ID
Core Demographics
Core Contact Information
Person Lifecycle/Record State
Person-Level Audit Context
Person Document Association
```

---

# 55. Person Module Does Not Own

The Person Module does not own:

```text
Membership Lifecycle
Organization Hierarchy
Family Governance
Attendance Rules
Mahila Governance
Kumari Governance
Kishor/Kishori Governance
Sevak Governance
Authentication Permissions
Office-Bearer Assignments
```

Those belong to their respective domains.

---

# 56. Person as Foundation Entity

The dependency direction is:

```text
Person
  │
  ├── Family
  ├── Membership
  ├── Attendance
  ├── Governance
  ├── Mahila
  ├── Kumari
  ├── Kishori
  ├── Kishor
  ├── Sevak
  ├── Applications
  └── Documents
```

The Person Module therefore sits below many business modules.

---

# 57. No Reverse Ownership

A downstream module shall not become the owner of Person identity merely
because it first encounters the person.

For example:

```
Membership
    ≠
Person Master

Family
    ≠
Person Master

Kumari
    ≠
Person Master
```

---

# 58. Person Identity Reuse

A single Person identity shall be reused across all applicable NSS ERP
modules.

This prevents:

```
Same Individual
    ↓
Multiple Person Records
```

---

# 59. Cross-Module Person Identity

Where a module requires an individual reference, it should use:

```
person_pk
```

rather than copying the person's identifying attributes into its own
master table.

---

# 60. Person and Business IDs

The system may expose:

```
person_id
```

to users and reports.

Internal relational references should use:

```
person_pk
```

according to the project database naming standard.

---

# 61. Person Module Data Integrity

The Person Module shall maintain:

```text
Unique Person Identity
Unique Person ID
Unique Mobile Where Supplied
At Least One Contact Method
Valid Core Demographic Data
Auditable Changes
Historical Identity Preservation
```

---

# 62. Person Module Security

Person information shall be protected through the common Authentication,
RBAC, authorization, and audit architecture.

The Person Module shall not create an independent security model.

---

# 63. Organizational Scope

Person records may be viewed or managed according to the user's authorized
organizational scope.

The scope model belongs to the common RBAC/Administration framework.

---

# 64. No Organization Ownership of Person

A Person does not become owned by a Sakha merely because the person is
associated with that Sakha.

Organizational association is a separate domain relationship.

---

# 65. No Membership Ownership of Person

A Membership record does not replace or own the Person identity.

The Membership Module references Person.

---

# 66. Person and Family Ownership

Family relationships reference Persons.

Family identity belongs to the Family Module.

---

# 67. Person and Historical Identity

Historical persons must remain representable even where they are no longer
active operationally.

This is important for:

* Historical office-bearers
* Family history
* Membership history
* Organizational history
* Heritage information

---

# 68. Person Design Philosophy

The Person Module follows:

```text
Person First
        ↓
Membership Later
        ↓
Domain Participation As Applicable
```

rather than:

```text
Member First
        ↓
Person Derived From Member
```

The first model is the frozen architectural principle.

---

# 69. Core Person Lifecycle

Conceptually:

```text
Person Created
      ↓
Person Maintained
      ↓
Person Participates in Zero or More Domains
      ↓
Person Remains Historically Identifiable
```

Person existence does not depend on membership.

---

# 70. Person Module Boundaries

The Person Module shall not duplicate:

```text
Membership Status
Organization Status
Family Status
Attendance Status
Governance Status
Authentication Status
```

Each belongs to its own domain.

---

# 71. Current Logical Scope

The current source identifies the core Person tables as:

```text
person
document_master
```

The project schema review explicitly lists these as the Person Module's
current tables.

Additional supporting entities shall not be introduced until justified by
the Person ERD/Table Design.

---

# 72. Design Decision — Person Core

The central Person entity is:

```text
person
```

All Person identity references originate from this entity.

---

# 73. Design Decision — Document Master

The current foundation includes:

```text
document_master
```

for document metadata/storage references associated with identity records.

The exact relationship and scope will be finalized in the Person ERD and
Table Design documents.

---

# 74. Design Decision — Person ≠ Member

This remains one of the most important frozen Person architecture rules.

```text
Person
  │
  ├── Member
  ├── Non-member
  ├── Family member
  ├── Youth participant
  ├── Applicant
  └── Historical person
```

All are valid Person identities.

---

# 75. Design Decision — Person ID

Every Person receives a permanent:

```text
person_id
```

generated through the centralized ID sequence mechanism.

---

# 76. Design Decision — Contact

The Person record requires at least one:

```text
Mobile
OR
Email
```

Mobile is unique when present.

Email is not globally unique.

---

# 77. Design Decision — Membership Independence

A Person may exist without a Membership record.

Membership creation is a separate business process.

---

# 78. Design Decision — Historical Preservation

Person identity is preserved even when the person is no longer active in
current operations.

---

# 79. Open Items for Person ERD/Table Design

The following must be resolved in the next Person documents rather than
assumed here:

* Exact address table structure
* Exact document relationship
* Complete demographic column set
* Person status representation
* Sensitive identity storage implementation
* Audit-column implementation
* Person merge/correction implementation
* Exact constraints and indexes

---

# 80. Final Person Design Principles

```text
✓ Person is the foundational individual identity

✓ Person ≠ Member

✓ A person may exist without membership

✓ A person may exist without a login account

✓ A person may exist without identity documents

✓ A person may be a family member without being an NSS member

✓ A person may participate in youth/domain modules without regular membership

✓ Person has a permanent internal UUID identity

✓ Person has a permanent human-readable Person ID

✓ Person ID is centrally generated

✓ Person ID is never reused

✓ Mobile is unique when supplied

✓ Email is not required to be unique

✓ At least one contact method is required

✓ Membership identity is separate from Person identity

✓ Sangha Sevi ID belongs to Membership

✓ Family references Person

✓ Governance references Person

✓ Attendance references Person where applicable

✓ Specialized modules reuse Person identity

✓ Person records are historically preserved

✓ Person operations are auditable

✓ Person does not own Organization hierarchy

✓ Person does not own Membership lifecycle

✓ Person does not own Governance assignments

✓ Person does not own Attendance rules

✓ Person does not own Authentication/RBAC

✓ Person Module remains a shared identity foundation
```

---

# 81. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
