# NSS ERP Person ERD

Version: 1.0

Status: DRAFT

---

# Person Module ERD

## person

Purpose:

Stores every individual known to NSS.

A person may or may not be a member.

---

Fields

person_pk UUID PK

person_code

first_name

middle_name

last_name

gender_pk

date_of_birth

mobile_number

email

marital_status_pk

photo_path

is_active

created_at

created_by

updated_at

updated_by

deleted_at

deleted_by

---

# person_address

Purpose:

Stores addresses for a person.

Reason:

A person may have:

Permanent Address

Current Address

Future Address Types

---

Fields

person_address_pk UUID PK

person_pk UUID FK

address_type_pk UUID FK

address_line_1

address_line_2

district_pk UUID FK

state_pk UUID FK

country_pk UUID FK

postal_code

is_active

created_at

updated_at

---

# gender_master

Examples

MALE

FEMALE

OTHER

---

# marital_status_master

Examples

UNMARRIED

MARRIED

WIDOWED

DIVORCED

SEPARATED

---

# address_type_master

Examples

PERMANENT

CURRENT

OFFICIAL

---

# Relationships

person

1
│
│
∞
person_address

---

gender_master

1
│
│
∞
person

---

marital_status_master

1
│
│
∞
person

---

address_type_master

1
│
│
∞
person_address

---

country_master

1
│
│
∞
person_address

---

state_master

1
│
│
∞
person_address

---

district_master

1
│
│
∞
person_address

---

# Membership Relationship

Person

1
│
│
0..1
Membership

Membership Module owns the relationship.

Person module does not store Sangha Sevi ID.

---

# Family Relationship

Person

∞
│
│
∞
Family Group

Family Module owns the relationship.

---

# Kumari Relationship

Person

1
│
│
∞
Kumari Participation

---

# Kishore Relationship

Person

1
│
│
∞
Kishore Participation

---

# Design Decisions

Person ≠ Member

Person Code Required

Membership Separate

Addresses Normalized

History Preserved

Audit Enabled

Soft Delete Enabled
