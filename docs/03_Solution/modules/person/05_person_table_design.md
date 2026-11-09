# NSS ERP — Person Table Design

**Document ID:** SOL-PER-004  
**Version:** 2.0.0  
**Status:** FROZEN  
**Amendment:** §49 (2026-11-04, GDR-011 — Proposed, owner approval pending) — the Aadhaar columns are now
written: `aadhaar_encrypted` holds an application-side AES-256-GCM blob (`v1:<key_id>:<nonce>:<ciphertext>`,
associated data = `person_pk`) instead of "pgcrypto-encrypted", and `aadhaar_hash` is an HMAC-SHA256 with a
separate secret pepper instead of a bare SHA-256. Columns, CHECKs and the unique index are unchanged (no
DDL change). The frozen text below is unchanged.  
**Module:** Person  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the NSS ERP Person Module.

It translates the Person:

- Module Design
- ERD
- Business Rules
- Common Database Standards

into a table-level logical design.

This document does not define:

- PostgreSQL DDL
- Django migrations
- Physical indexes
- Database triggers
- API implementation
- UI implementation

---

# 2. Current Person Table Scope

The Person Module contains two tables:

```text
person
person_address
```

`document_master` was originally defined here but has been reassigned to the
Foundation Module as a shared document registry (DOC-ARCH-001).
Person remains a consumer of `document_master` through explicit FK
relationships (e.g. `photo_document_master_pk`).

`person_address` stores zero or more typed addresses per Person, with
address types drawn from the Foundation `master_data` framework.

---

# 3. Core Design Principle

The Person table represents:

```text
ONE INDIVIDUAL
        ↓
ONE PERSON IDENTITY
```

Membership, Family, Governance, Attendance, Mahila, Kumari, Kishori,
Kishor, and Sevak records reference Person identity where applicable.

The Person table is not the Membership table.

---

# 4. Database Naming Standards

The Person design follows the project database conventions.

## Internal Primary Key

```text
<table_name>_pk
```

Example:

```text
person_pk
```

## Business Identifier

```text
<table_name>_id
```

Example:

```text
person_id
```

## Foreign Key

Foreign keys reference internal primary keys.

Example:

```text
person_pk
```

rather than:

```text
person_id
```

The project database standard explicitly establishes UUID internal keys and
human-readable business IDs.

---

# 5. Table 1 — `person`

## Purpose

`person` is the authoritative identity table for an individual known to
the NSS ERP.

A Person may or may not have an NSS Membership.

---

# 6. `person` — Logical Columns

| #  | Column                                   |    Required | Key    | Group              | Description                                |
| -- | ---------------------------------------- | ----------: | ------ | ------------------ | ------------------------------------------ |
| 1  | `person_pk`                              |         Yes | PK     | Identity           | Internal Person identity (UUID)            |
| 2  | `person_id`                              |         Yes | UNIQUE | Identity           | Permanent human-readable Person ID         |
| 3  | `first_name`                             |         Yes | —      | Demographics       | First name                                 |
| 4  | `middle_name`                            |          No | —      | Demographics       | Middle name                                |
| 5  | `last_name`                              |          No | —      | Demographics       | Last name                                  |
| 6  | `date_of_birth`                          |          No | —      | Demographics       | Date of birth                              |
| 7  | `date_of_death`                          |          No | —      | Demographics       | Date of death                              |
| 8  | `gender_master_data_pk`                  |          No | FK     | Demographics       | Gender (Foundation master_data)            |
| 9  | `marital_status_master_data_pk`          |          No | FK     | Demographics       | Marital status (Foundation master_data)    |
| 10 | `blood_group_master_data_pk`             |          No | FK     | Demographics       | Blood group (Foundation master_data)       |
| 11 | `country_phone_code`                     | Conditional | —      | Contact            | International dialling code (e.g. +91)     |
| 12 | `mobile_number`                          | Conditional | UNIQUE | Contact            | Mobile contact number                      |
| 13 | `email`                                  | Conditional | —      | Contact            | Email contact                              |
| 14 | `aadhaar_encrypted`                      |          No | —      | Sensitive Identity | Aadhaar full value (encrypted, BYTEA)      |
| 15 | `aadhaar_hash`                           |          No | —      | Sensitive Identity | SHA-256 hash for lookup without decryption |
| 16 | `aadhaar_last4`                          |          No | —      | Sensitive Identity | Last 4 digits for masked display           |
| 17 | `photo_document_master_pk`               |          No | FK     | Photo              | Photo metadata (Foundation document_master)|
| 18 | `emergency_contact_name`                 |          No | —      | Emergency Contact  | Emergency contact person's name            |
| 19 | `emergency_contact_phone`                |          No | —      | Emergency Contact  | Emergency contact phone number             |
| 20 | `emergency_relationship_master_data_pk`  |          No | FK     | Emergency Contact  | Relationship type (Foundation master_data) |
| 21 | `remarks`                                |          No | —      | Other              | Free-text remarks                          |
| 22 | `is_active`                              |         Yes | —      | Lifecycle          | Person record operational state            |
| 23 | `created_at`                             |         Yes | —      | Audit              | Creation timestamp                         |
| 24 | `created_by_sangha_sevi_pk`              |          No | FK     | Audit              | Creating user/member reference             |
| 25 | `updated_at`                             |          No | —      | Audit              | Last update timestamp                      |
| 26 | `updated_by_sangha_sevi_pk`              |          No | FK     | Audit              | Updating user/member reference             |
| 27 | `deleted_at`                             |          No | —      | Audit              | Soft-delete timestamp                      |
| 28 | `deleted_by_sangha_sevi_pk`              |          No | FK     | Audit              | Deleting user/member reference             |

**28 physical columns.** Columns 11–12 (country_phone_code + mobile_number)
are an all-or-nothing pair. Columns 14–16 (Aadhaar) are an all-or-nothing
triplet. At least one of mobile_number (12) or email (13) must be present.

---

# 7. `person_pk`

`person_pk` is the internal primary key.

Requirements:

* UUID
* Unique
* Immutable
* Used for relational references
* Not the normal human-facing identifier

The project database standard explicitly freezes UUIDs for internal primary
keys.

---

# 8. `person_id`

`person_id` is the permanent human-readable Person business identifier.

Illustrative values:

```text
P00000001
P00000002
P00000003
```

The project source establishes centralized ID generation using
`id_sequence_master`.

---

# 9. Person ID Rules

`person_id` shall be:

* Unique
* System-generated
* Permanent
* Stable
* Never reused

It shall not be generated through application-local counters.

---

# 10. `first_name`

Stores the person's first/given name.

This is a Person attribute and does not constitute identity.

---

# 11. `middle_name`

Stores an optional middle name.

A Person may exist without a middle name.

---

# 12. `last_name`

Stores the person's family/last name where applicable.

The project does not require that every Person have a conventional last name.

---

# 13. Name and Identity

Changing:

```text
first_name
middle_name
last_name
```

does not create a new Person.

The permanent identity remains:

```text
person_pk
person_id
```

---

# 14. `gender_master_data_pk`

References Foundation `master_data` where the category is GENDER.

Gender values (MALE, FEMALE, OTHER) are maintained through the common
`master_category` / `master_data` framework rather than a Person-specific
`gender_master` table.

The Person Module does not own the global gender master.

---

# 15. Gender Boundary

The Person table stores the Person's gender reference.

It does not use gender to determine:

* Membership
* Organization
* Authentication
* Governance position

Those rules belong to their respective domains.

---

# 16. `date_of_birth`

Stores the Person's date of birth where known.

Date of birth is a Person-level demographic attribute.

---

# 17. Date of Birth and Membership

Person creation does not automatically require the Membership-specific
date-of-birth requirements.

Where Membership approval requires DOB, Membership rules govern that
requirement.

---

# 18. `date_of_death`

Stores date of death where known.

It preserves historical identity information.

---

# 19. Date of Death and Deletion

Recording a date of death does not mean:

```text
DELETE PERSON
```

The Person remains historically identifiable.

---

# 20. `mobile_number`

Stores the Person's mobile contact number.

The current Person business rule establishes uniqueness when supplied.

---

# 21. Mobile Number Nullability

`mobile_number` may be NULL if the Person has a valid email address.

---

# 22. Mobile Number Uniqueness

When present:

```text
mobile_number
```

must identify at most one Person.

The exact physical implementation of NULL-aware uniqueness belongs to
PostgreSQL schema design.

---

# 23. `email`

Stores the Person's email address where available.

---

# 24. Email Nullability

Email may be NULL when mobile number is present.

---

# 25. Email Uniqueness

Email is not globally unique.

Multiple Person records may legitimately share an email address.

---

# 26. Contact Requirement

The Person record must satisfy:

```text
mobile_number IS NOT NULL
OR
email IS NOT NULL
```

Therefore:

```text
mobile_number IS NULL
AND
email IS NULL
```

is invalid.

The physical PostgreSQL CHECK constraint will be defined later.

---

# 27. Contact Normalization

The final physical implementation should normalize mobile/email values
according to the project's common data-quality and internationalization
standards.

This document does not prescribe a specific normalization algorithm.

---

# 28. `is_active`

Represents the operational state of the Person record.

It is distinct from:

```text
Membership Status
Organization Status
Authentication Status
```

---

# 29. Person Status Boundary

`is_active` shall not be interpreted as:

```text
NSS Membership Active
```

A Person may remain active as a Person even when Membership is inactive or
has ended.

---

# 30. Audit Columns

The project database standard establishes common audit fields including:

```text
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

and:

```text
is_active
```

for major transactional records.

The Person table follows that standard.

---

# 31. `created_at`

Records when the Person record was created.

---

# 32. `created_by_sangha_sevi_pk`

Identifies the authorized NSS user/member responsible for creating the
record where the common audit framework requires such attribution.

The exact authentication/audit implementation belongs to the common
Foundation/Security architecture.

---

# 33. `updated_at`

Records the latest update timestamp.

---

# 34. `updated_by_sangha_sevi_pk`

Identifies the authorized user/member responsible for the latest update
where the common audit framework requires attribution.

---

# 35. `deleted_at`

Records the timestamp of a soft-delete operation.

---

# 36. `deleted_by_sangha_sevi_pk`

Identifies the authorized user/member responsible for the soft-delete
operation where applicable.

---

# 37. Soft Delete

The project standard prohibits ordinary physical deletion of major
transactional records and uses soft-delete semantics.

For Person:

```text
is_active = FALSE
deleted_at = timestamp
```

may be used according to the common lifecycle/audit framework.

---

# 38. Historical Person Preservation

A Person record should remain available when historical relationships require
it.

Examples:

* Former Member
* Historical office-bearer
* Family history
* Historical attendance
* Historical participation

---

# 39. Person-to-Membership Relationship

The Person table is referenced by Membership.

Conceptually:

```text
person
   1
   │
   │ 0..1
   ▼
sangha_sevi
```

The Membership Module owns the Membership record.

---

# 40. No `sangha_sevi_id` in Person

The Person table shall not contain:

```text
sangha_sevi_id
```

as the Person's identity.

Sangha Sevi ID belongs to Membership.

---

# 41. Person-to-Family Relationship

Family tables reference:

```text
person_pk
```

The Person table does not contain family-group ownership fields unless
explicitly established by the Family design.

---

# 42. Person-to-Organization Relationship

The Person table does not own:

```text
organization_pk
```

as a permanent Person identity attribute.

Organizational association belongs to the appropriate domain relationship.

This prevents a Person from being incorrectly treated as belonging to only
one Organization.

---

# 43. Person-to-Governance Relationship

Governance tables reference Person identity.

The Person table does not contain:

```text
position_pk
governing_body_pk
office_bearer_pk
```

Governance owns those relationships.

---

# 44. Person-to-Attendance Relationship

Attendance records may reference:

```text
person_pk
```

The Person table does not store attendance history.

Attendance owns attendance records.

---

# 45. Specialized Module Relationships

The following modules may reference `person_pk`:

```text
Mahila
Kumari
Kishori
Kishor
Sevak
```

They shall not create duplicate Person master records.

---

# 46. No Specialized Person Identity

The following concepts shall not become separate Person identities:

```text
Mahila Person
Kumari Person
Kishori Person
Kishor Person
Sevak Person
```

They are domain participation records associated with the same Person.

---

# 47. Person Address

Person address is implemented as a separate table: `person_address`.

The `person_address` table stores zero or more typed addresses per Person.
Address types are drawn from Foundation `master_data` (category
ADDRESS_TYPE) via `address_type_master_data_pk`.

A primary-address uniqueness constraint ensures at most one primary address
per active Person record.

See Table 2 below for the full `person_address` logical design.

---

# 48. Address Design Status

```text
Person Address Concept
    = FROZEN

Physical Address Structure
    = FROZEN (person_address table)
```

The address model has been resolved. `person_address` is a Person Module
table with its own DDL file (`03_person_address.sql`).

---

# 49. Aadhaar / Sensitive Identity Data

Aadhaar is implemented as three all-or-nothing columns on `person`:

```text
aadhaar_encrypted   BYTEA     Full Aadhaar (pgcrypto-encrypted)
aadhaar_hash        VARCHAR   SHA-256 hash (lookup without decryption)
aadhaar_last4       VARCHAR   Last 4 digits (masked display)
```

All three must be NULL or all three must be populated (enforced by CHECK
constraint `chk_person_aadhaar_consistency`).

A partial unique index on `aadhaar_hash` ensures one Aadhaar per Person
when present.

Format validation: `aadhaar_last4` must match `^[0-9]{4}$` when present.

Sensitive identity data follows the project's security standards. Full
Aadhaar values are never exposed in normal UI/reporting.

---

# 50. Photo

Person photo is implemented as a FK to Foundation's `document_master`:

```text
photo_document_master_pk  UUID  FK → nss.document_master
```

The photo binary is stored externally (managed by the document/storage
architecture). This FK points to the document metadata record.

This avoids embedding binary data into the core identity table.

---

# 51. Emergency Contact

Emergency contact is implemented as three inline columns on `person`:

```text
emergency_contact_name                    VARCHAR(200)
emergency_contact_phone                   VARCHAR(20)
emergency_relationship_master_data_pk     UUID FK → nss.master_data
```

The relationship type references Foundation `master_data` (category
RELATIONSHIP_TYPE).

Format validation: `emergency_contact_phone` must match `^[0-9]{7,15}$`
when present.

---

# 52. Blood Group

Blood group is implemented as a FK to Foundation `master_data`:

```text
blood_group_master_data_pk  UUID  FK → nss.master_data
```

Blood group values (A_POSITIVE, A_NEGATIVE, B_POSITIVE, B_NEGATIVE,
AB_POSITIVE, AB_NEGATIVE, O_POSITIVE, O_NEGATIVE) are maintained through
the Foundation `master_category` / `master_data` framework under
category BLOOD_GROUP.

---

# 53. Table 2 — `document_master`

## Ownership Reassignment (DOC-ARCH-001)

`document_master` has been reassigned to the Foundation Module as a shared
document registry. The logical design below is preserved for reference, but
Foundation is the authoritative DDL owner.

Person references `document_master` through an explicit FK relationship
(exact pattern — direct FK or junction table — to be determined during
Person DDL design).

## Purpose

Stores document metadata associated with Person identity and the project's
document-management framework.

The document itself is not the Person identity.

---

# 54. `document_master` — Logical Columns

The current source establishes the document concept and metadata such as:

* Document Type
* Storage Path
* Version
* Checksum
* Uploaded By

The following logical design represents those concepts without claiming a
final physical schema:

| Column                       |    Required | Key | Description                     |
| ---------------------------- | ----------: | --- | ------------------------------- |
| `document_pk`                |         Yes | PK  | Internal document identity      |
| `person_pk`                  | Conditional | FK  | Person associated with document |
| `document_type_pk`           |         Yes | FK  | Controlled document type        |
| `document_number`            |          No | —   | Document/reference number       |
| `storage_path`               |         Yes | —   | Storage reference               |
| `version`                    |         Yes | —   | Document version                |
| `checksum`                   |          No | —   | File integrity checksum         |
| `uploaded_at`                |         Yes | —   | Upload timestamp                |
| `uploaded_by_sangha_sevi_pk` |          No | FK  | Uploading user/member           |
| `is_active`                  |         Yes | —   | Current document state          |
| `created_at`                 |         Yes | —   | Creation timestamp              |
| `updated_at`                 |         Yes | —   | Last update timestamp           |

Only the concepts supported by the current source are represented here.

---

# 55. `document_pk`

Internal primary key for the document record.

The project database convention uses UUID internal primary keys.

---

# 56. `person_pk` in `document_master`

Where a document belongs to a Person, `person_pk` identifies the associated
Person.

The document references the Person's internal primary key, not:

```text
person_id
```

---

# 57. Document Type

`document_type_pk` references the common controlled document-type master.

The Person Module does not independently maintain a duplicate document-type
master.

---

# 58. `document_number`

Optional document/reference number where applicable.

Not all documents require an external document number.

---

# 59. `storage_path`

Stores the logical reference to the physical document location.

The Person Module does not prescribe whether storage is:

* Local filesystem
* Object storage
* Another approved document repository

---

# 60. `version`

Represents the document version where document versioning applies.

Document versioning is separate from Person identity.

---

# 61. `checksum`

May store a checksum used to verify document integrity.

The exact algorithm is an implementation decision.

---

# 62. `uploaded_at`

Records when the document was uploaded/registered.

---

# 63. `uploaded_by_sangha_sevi_pk`

Identifies the authorized uploader where the common audit/security framework
requires attribution.

---

# 64. Document Active State

`is_active` identifies whether the document record is currently active.

A superseded document may remain historically preserved.

---

# 65. Document History

Document history shall not automatically delete the Person record.

Replacing a document does not replace Person identity.

---

# 66. Person-to-Document Cardinality

The logical relationship is:

```text
PERSON
   1
   │
   │ 0..N
   ▼
DOCUMENT_MASTER
```

A Person may have no documents or multiple documents.

---

# 67. Document-to-Person Ownership

A Person document is associated with a Person identity.

A document does not create a new Person.

---

# 68. Common Master Dependencies

The Person Module reuses common Foundation masters where applicable:

```text
Gender
Document Type
Country
State/Province
District
City/Village
Pincode
```

The exact common master names shall follow the final Foundation design.

---

# 69. Common ID Sequence Dependency

Person business IDs depend on:

```text
id_sequence_master
```

The Person Module shall not maintain its own sequence mechanism.

---

# 70. Common Audit Dependency

Person and document audit fields follow the common project audit standard.

The Person Module shall not create a separate audit framework.

---

# 71. Security Dependency

Person and document access follows the common:

```text
Authentication
RBAC
Authorization
Audit
```

architecture.

---

# 72. Foreign Key Summary

| Child Table       | Column                                  | Parent                               |
| ----------------- | --------------------------------------- | ------------------------------------ |
| `person`          | `gender_master_data_pk`                 | `nss.master_data` (GENDER)           |
| `person`          | `marital_status_master_data_pk`         | `nss.master_data` (MARITAL_STATUS)   |
| `person`          | `blood_group_master_data_pk`            | `nss.master_data` (BLOOD_GROUP)      |
| `person`          | `photo_document_master_pk`              | `nss.document_master`                |
| `person`          | `emergency_relationship_master_data_pk` | `nss.master_data` (RELATIONSHIP_TYPE)|
| `person`          | `created_by_sangha_sevi_pk`             | Membership/User identity (Pass 2)    |
| `person`          | `updated_by_sangha_sevi_pk`             | Membership/User identity (Pass 2)    |
| `person`          | `deleted_by_sangha_sevi_pk`             | Membership/User identity (Pass 2)    |
| `person_address`  | `person_pk`                             | `nss.person`                         |
| `person_address`  | `address_type_master_data_pk`           | `nss.master_data` (ADDRESS_TYPE)     |
| `person_address`  | `country_pk`                            | `nss.country`                        |
| `person_address`  | `state_pk`                              | `nss.state`                          |
| `person_address`  | `district_pk`                           | `nss.district`                       |
| `person_address`  | `city_village_pk`                       | `nss.city_village`                   |
| `person_address`  | `postal_code_pk`                        | `nss.postal_code`                    |

Audit actor FKs (`*_by_sangha_sevi_pk`) are included as nullable columns
in Pass 1. Their FK constraints are deferred to Pass 2 (after the
`sangha_sevi` table exists in the Membership module).

---

# 73. Logical Relationship Model

```mermaid
erDiagram

    PERSON ||--o{ PERSON_ADDRESS : "has"
    PERSON ||--o{ DOCUMENT_MASTER : "has"

    PERSON {
        UUID person_pk PK
        VARCHAR person_id UK
        VARCHAR first_name
        VARCHAR middle_name
        VARCHAR last_name
        DATE date_of_birth
        DATE date_of_death
        UUID gender_master_data_pk FK
        UUID marital_status_master_data_pk FK
        UUID blood_group_master_data_pk FK
        VARCHAR country_phone_code
        VARCHAR mobile_number UK
        VARCHAR email
        BYTEA aadhaar_encrypted
        VARCHAR aadhaar_hash
        VARCHAR aadhaar_last4
        UUID photo_document_master_pk FK
        VARCHAR emergency_contact_name
        VARCHAR emergency_contact_phone
        UUID emergency_relationship_master_data_pk FK
        TEXT remarks
        BOOLEAN is_active
        TIMESTAMP created_at
        UUID created_by_sangha_sevi_pk FK
        TIMESTAMP updated_at
        UUID updated_by_sangha_sevi_pk FK
        TIMESTAMP deleted_at
        UUID deleted_by_sangha_sevi_pk FK
    }

    PERSON_ADDRESS {
        UUID person_address_pk PK
        UUID person_pk FK
        UUID address_type_master_data_pk FK
        VARCHAR address_line_1
        VARCHAR address_line_2
        VARCHAR landmark
        UUID district_pk FK
        UUID state_pk FK
        UUID country_pk FK
        UUID city_village_pk FK
        UUID postal_code_pk FK
        BOOLEAN is_primary
        BOOLEAN is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
        TIMESTAMP deleted_at
    }

    DOCUMENT_MASTER {
        UUID document_master_pk PK
        UUID document_type_master_data_pk FK
        VARCHAR storage_path
        VARCHAR checksum
        INTEGER version
        BOOLEAN is_active
        TIMESTAMP uploaded_at
    }
```

---

# 74. Membership Relationship — External

The Person Module does not own the Membership table.

Logical relationship:

```text
PERSON
  1
  │
  │ 0..1
  ▼
MEMBERSHIP
```

Membership is a separate module.

---

# 75. Family Relationship — External

The Person Module does not own Family relationships.

Logical relationship:

```text
PERSON
  1
  │
  │ 0..N
  ▼
FAMILY RELATIONSHIPS
```

Family is a separate module.

---

# 76. Governance Relationship — External

Governance references Person identity.

The Person table does not contain governance assignment fields.

---

# 77. Attendance Relationship — External

Attendance references Person identity where applicable.

The Person table does not contain attendance records.

---

# 78. Specialized Module Relationship — External

Mahila, Kumari, Kishori, Kishor, and Sevak may reference Person identity.

No duplicate Person table is created in those modules.

---

# 79. Identity Integrity Requirements

The logical design requires:

```text
person_pk
    → unique

person_id
    → unique

mobile_number
    → unique when supplied

mobile_number OR email
    → at least one required

document person_pk
    → valid Person reference

document type
    → valid controlled reference
```

---

# 80. Historical Integrity

The Person table must preserve identity across:

```text
Name Change
Address Change
Contact Change
Membership Change
Organization Change
Family Change
Participation Change
```

---

# 81. No Person Duplication

The physical database and application layer should work together to prevent
creation of duplicate Person identities.

Potential duplicate detection is an application/business concern and is not
reduced to a single database constraint.

---

# 82. Person Merge

Person merge is not a simple table operation.

If implemented later, the process must preserve all affected relationships
and historical information.

The merge workflow is outside the current table-design scope.

---

# 83. Person Deletion

Physical deletion is not the normal Person lifecycle.

Historical records shall remain available where required.

---

# 84. Auditability

At minimum, the Person design supports:

```text
Created
Updated
Soft Deleted
```

with responsible-user attribution through the common audit framework.

---

# 85. Security

Sensitive Person information and documents shall be protected by the
common security framework.

The Person table shall not expose sensitive values unnecessarily.

---

# 86. Person Table Summary

```text
person (28 columns)
│
├── person_pk
├── person_id
│
├── first_name
├── middle_name
├── last_name
├── date_of_birth
├── date_of_death
├── gender_master_data_pk          → nss.master_data (GENDER)
├── marital_status_master_data_pk  → nss.master_data (MARITAL_STATUS)
├── blood_group_master_data_pk     → nss.master_data (BLOOD_GROUP)
│
├── country_phone_code
├── mobile_number
├── email
│
├── aadhaar_encrypted
├── aadhaar_hash
├── aadhaar_last4
│
├── photo_document_master_pk       → nss.document_master
│
├── emergency_contact_name
├── emergency_contact_phone
├── emergency_relationship_master_data_pk → nss.master_data (RELATIONSHIP_TYPE)
│
├── remarks
│
├── is_active
│
├── created_at
├── created_by_sangha_sevi_pk
├── updated_at
├── updated_by_sangha_sevi_pk
├── deleted_at
└── deleted_by_sangha_sevi_pk
```

---

# 87. Document Master Summary

```text
document_master
│
├── document_pk
├── person_pk
├── document_type_pk
├── document_number
├── storage_path
├── version
├── checksum
├── uploaded_at
├── uploaded_by_sangha_sevi_pk
├── is_active
├── created_at
└── updated_at
```

---

# 88. Current Table Count

```text
Person Module
────────────────────────────
person                  1
person_address          1
────────────────────────────
TOTAL                   2
```

`document_master` (previously counted here) is now owned by Foundation
(DOC-ARCH-001). Person references it via `photo_document_master_pk`.

---

# 89. Explicitly Not Added

The following are not added as frozen Person tables/columns without further
approved design:

```text
person_address_history
person_merge_history
person_status_master
```

The following items from the earlier version of this document have been
resolved and are now FROZEN:

```text
person_address           → FROZEN (Table 2, 03_person_address.sql)
aadhaar_encrypted        → FROZEN (person column 14)
aadhaar_hash             → FROZEN (person column 15)
aadhaar_last4            → FROZEN (person column 16)
photo_path               → FROZEN as photo_document_master_pk (person column 17)
blood_group              → FROZEN as blood_group_master_data_pk (person column 10)
emergency_contact        → FROZEN as 3 columns (person columns 18–20)
marital_status           → FROZEN as marital_status_master_data_pk (person column 9)
```

---

# 90. Important Design Boundary

This document intentionally distinguishes:

```text
SOURCE-SUPPORTED DESIGN
        from
IMPLEMENTATION ASSUMPTIONS
```

Only source-supported Person structures are treated as frozen.

---

# 91. Physical Schema Boundary

This document does not define:

```text
CREATE TABLE
ALTER TABLE
CHECK CONSTRAINT SQL
INDEX SQL
TRIGGER SQL
PostgreSQL datatype selection beyond established PK conventions
Django models
FastAPI endpoints
UI
```

These belong to the implementation stage.

---

# 92. Person Module Final Logical Model

```text
                    PERSON
                      │
                      │
             ┌────────┴────────┐
             │                 │
             ▼                 ▼
       PERSON IDENTITY     DOCUMENT MASTER
             │
             │
       ┌─────┼─────┬──────────┬──────────┐
       ▼     ▼     ▼          ▼          ▼
   FAMILY  MEMBER  GOV     ATTENDANCE  SPECIALIZED
                               │
                     ┌─────────┼─────────┐
                     ▼         ▼         ▼
                   Mahila    Kumari    Sevak
```

---

# 93. Final Person Table Principles

```text
✓ Person is the core individual identity

✓ Person ≠ Member

✓ Person Module contains 2 frozen tables (person, person_address)

✓ person is the central Person table (28 physical columns)

✓ person_address stores typed addresses per Person

✓ document_master stores document metadata (Foundation-owned)

✓ person_pk is the internal UUID identity

✓ person_id is the human-readable business identity

✓ person_id is unique

✓ person_id is permanent

✓ person_id is centrally generated

✓ person_id is never reused

✓ Foreign keys reference person_pk

✓ Mobile is unique when supplied (NULL-aware partial index)

✓ Email is not globally unique

✓ At least one contact method is required

✓ Gender, marital status, blood group use Foundation master_data FKs

✓ Aadhaar uses encrypted + hash + last4 (all-or-nothing)

✓ Photo references Foundation document_master

✓ Emergency contact uses Foundation master_data for relationship type

✓ Person lifecycle: is_active + date_of_death + deleted_at (no status column)

✓ Person identity survives Membership changes

✓ Person identity survives organizational changes

✓ Person identity survives family changes

✓ Person identity survives demographic corrections

✓ Person records are historically preserved

✓ Person documents reference Person identity

✓ Person does not own Membership

✓ Person does not own Family

✓ Person does not own Organization

✓ Person does not own Governance

✓ Person does not own Attendance

✓ Specialized modules reuse Person identity

✓ Common audit framework is reused

✓ Common security framework is reused

✓ Common master-data framework is reused

✓ Format validation CHECK constraints are part of the DDL
```

---

# 94. Open Items Before Physical Person Schema

| Item                          | Status                          |
| ----------------------------- | ------------------------------- |
| Person address structure      | FROZEN (person_address table)   |
| Sensitive identity storage    | FROZEN (Aadhaar triplet)        |
| Photo/document implementation | FROZEN (photo_document_master_pk) |
| Blood group                   | FROZEN (blood_group_master_data_pk) |
| Emergency contact             | FROZEN (3 inline columns)       |
| Person status vocabulary      | CLOSED (no separate status column — lifecycle derived from is_active + date_of_death + deleted_at) |
| Person merge history          | OPEN                            |
| Exact document versioning     | OPEN (Foundation-owned)         |
| Physical constraints          | FROZEN (DDL v2.0)               |
| Physical indexes              | FROZEN (DDL v2.0)               |

---

# 95. Status

```text
DOCUMENT STATUS:
FROZEN

VERSION:
2.0.0

FROZEN DATE:
2026-09-11
```

---

# End of Document
