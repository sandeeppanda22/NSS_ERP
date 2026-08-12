# NSS ERP Person Table Design

Version: 1.1

Status: DRAFT

---

# Purpose

Defines the physical table structure for the Person Module.

Business Rules and ERD must be approved before modifying this document.

---

# Design Principles

* Person ≠ Member
* Person Code is the primary business identifier
* * Mobile Number + Country Phone Code must be unique
* International mobile numbers supported
* Email is not required to be unique
* At least one contact method is mandatory
* Date of Birth is optional for Person records
* Date of Birth becomes mandatory before Membership approval
* Multiple addresses supported
* Soft delete enabled
* Audit enabled
* Master Data driven architecture
* Photo and document storage deferred to Document Management Module

---

# Table 1: gender_master

## Purpose

Stores supported genders.

---

## Columns

gender_pk UUID PRIMARY KEY

gender_code VARCHAR(20) NOT NULL

gender_name VARCHAR(50) NOT NULL

display_order INTEGER NOT NULL

created_at TIMESTAMPTZ NOT NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

## Seed Data

MALE

FEMALE

OTHER

---

## Unique Constraints

gender_code

gender_name

---

## Indexes

is_active

---

# Table 2: marital_status_master

## Purpose

Stores marital status values.

---

## Columns

marital_status_pk UUID PRIMARY KEY

marital_status_code VARCHAR(30) NOT NULL

marital_status_name VARCHAR(100) NOT NULL

display_order INTEGER NOT NULL

created_at TIMESTAMPTZ NOT NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

## Seed Data

UNMARRIED

MARRIED

WIDOWED

DIVORCED

SEPARATED

---

## Unique Constraints

marital_status_code

marital_status_name

---

## Indexes

is_active

---

# Table 3: address_type_master

## Purpose

Stores address classifications.

---

## Columns

address_type_pk UUID PRIMARY KEY

address_type_code VARCHAR(30) NOT NULL

address_type_name VARCHAR(100) NOT NULL

display_order INTEGER NOT NULL

created_at TIMESTAMPTZ NOT NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

## Seed Data

PERMANENT

CURRENT

OFFICIAL

---

## Unique Constraints

address_type_code

address_type_name

---

## Indexes

is_active

---

# Table 4: person

## Purpose

Stores every individual known to NSS.

A Person may or may not be a Member.

---

## Columns

person_pk UUID PRIMARY KEY

person_code VARCHAR(20) NOT NULL

first_name VARCHAR(100) NOT NULL

middle_name VARCHAR(100) NULL

last_name VARCHAR(100) NULL

gender_pk UUID NOT NULL

date_of_birth DATE NULL

country_phone_code VARCHAR(10) NULL

mobile_number VARCHAR(20) NULL

email VARCHAR(255) NULL

marital_status_pk UUID NULL

remarks TEXT NULL

created_at TIMESTAMPTZ NOT NULL

updated_at TIMESTAMPTZ NULL

deleted_at TIMESTAMPTZ NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

## Foreign Keys

gender_pk
→ gender_master.gender_pk

marital_status_pk
→ marital_status_master.marital_status_pk

---

## Unique Constraints

person_code

(country_phone_code, mobile_number)

---

## Check Constraints

### Contact Information Rule

At least one contact method must exist.

UNIQUE
(
country_phone_code,
mobile_number
)

CHECK
(
mobile_number IS NOT NULL
OR
email IS NOT NULL
)

CHECK
(
(
country_phone_code IS NULL
AND mobile_number IS NULL
)
OR
(
country_phone_code IS NOT NULL
AND mobile_number IS NOT NULL
)
)


---

## Indexes

person_code

first_name

last_name

mobile_number

email

gender_pk

marital_status_pk

is_active

---

## Business ID Examples

P00000001

P00000002

P00000003

Generated through:

id_sequence_master

---

## Frozen Business Rules

### Name Rules

first_name NOT NULL

middle_name NULL

last_name NULL

---

### Gender Rule

gender_pk NOT NULL

---

### Date of Birth Rule

date_of_birth NULL ALLOWED

Date of Birth becomes mandatory before Membership approval.

---

### Mobile Number Rule

country_phone_code + mobile_number UNIQUE

mobile_number NULL ALLOWED

country_phone_code NULL ALLOWED

Both values must be supplied together.

---

### Email Rule

email NOT UNIQUE

email NULL ALLOWED

---

### Contact Information Rule

Both mobile_number and email cannot be NULL simultaneously.

---

### Membership Rule

Person records shall not store:

* Sangha Sevi ID
* Membership Type
* Membership Status

These belong to the Membership Module.

---

### Photo Rule

Photo storage is deferred to the Document Management Module.

No photo column shall be stored in the Person table.

---

### Audit Rule

Audit foreign key ownership is deferred until Membership and Authentication modules are frozen.

Current columns:

created_at

updated_at

deleted_at

---

# Table 5: person_address

## Purpose

Stores addresses belonging to a Person.

A Person may have multiple addresses.

---

## Columns

person_address_pk UUID PRIMARY KEY

person_pk UUID NOT NULL

address_type_pk UUID NOT NULL

address_line_1 VARCHAR(200) NOT NULL

address_line_2 VARCHAR(200) NULL

landmark VARCHAR(255) NULL

city_village_postal_code_map_pk UUID NOT NULL

is_primary BOOLEAN NOT NULL DEFAULT FALSE

created_at TIMESTAMPTZ NOT NULL

updated_at TIMESTAMPTZ NULL

deleted_at TIMESTAMPTZ NULL

is_active BOOLEAN NOT NULL DEFAULT TRUE

---

## Foreign Keys

person_pk
→ person.person_pk

address_type_pk
→ address_type_master.address_type_pk

city_village_postal_code_map_pk
→ city_village_postal_code_map.city_village_postal_code_map_pk

---

## Indexes

person_pk

address_type_pk

city_village_postal_code_map_pk

is_active

---

## Address Rules

A Person may designate one address as the Primary Address.

At any point in time, only one address may be designated as the Primary Address.

The Primary Address may be changed by an authorized user.

When a new address is marked as Primary, the system shall automatically remove the Primary designation from the previous address.

The database shall enforce that no Person can have more than one Primary Address simultaneously.

Implementation:

CREATE UNIQUE INDEX uq_person_primary_address
ON person_address(person_pk)
WHERE is_primary = TRUE;

---

# Deferred Features

The following items are intentionally excluded from Person Module v1:

* Person Photo
* Aadhaar
* Passport
* Voter ID
* Driving License
* Educational Documents
* Employment Documents
* Contact History
* Merge History

These will be implemented through future modules.

---

# Future Modules

## Document Management Module

Will support:

* Person Photo
* Aadhaar
* Passport
* Voter ID
* Other Attachments

---

## Future Tables

person_document

person_contact_history

person_merge_history

person_photo_history

These are outside the scope of Person Module v1.
