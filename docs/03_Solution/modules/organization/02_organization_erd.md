# NSS ERP Organization ERD

Version: 1.0

Status: DRAFT

---

# Organization Module ERD

## organization_type_master

Purpose:

Defines organization categories.

Fields:

organization_type_pk UUID PK

organization_type_code

organization_type_name

display_order

is_active

---

## organization_status_master

Purpose:

Defines organization lifecycle status.

Fields:

organization_status_pk UUID PK

status_code

status_name

display_order

is_active

---

## organization

Purpose:

Stores all NSS organizations.

Fields:

organization_pk UUID PK

organization_id

organization_name

organization_type_pk FK

parent_organization_pk FK

organization_status_pk FK

established_date

remarks

created_at

created_by_sangha_sevi_pk

updated_at

updated_by_sangha_sevi_pk

deleted_at

deleted_by_sangha_sevi_pk

is_active

---

## organization_address

Purpose:

Stores organization addresses.

Fields:

organization_address_pk UUID PK

organization_pk FK

address_line_1

address_line_2

district_pk FK

state_pk FK

country_pk FK

postal_code

created_at

created_by_sangha_sevi_pk

updated_at

updated_by_sangha_sevi_pk

deleted_at

deleted_by_sangha_sevi_pk

is_active

---

# Relationships

organization_type_master

1
│
│
∞
organization

---

organization_status_master

1
│
│
∞
organization

---

organization

1
│
│
∞
organization

(parent_organization_pk)

---

organization

1
│
│
∞
organization_address

---

country_master

1
│
│
∞
organization_address

---

state_master

1
│
│
∞
organization_address

---

district_master

1
│
│
∞
organization_address

---

# Hierarchy Example

KENDRA
organization_pk = K1

```
↓
```

ANCHALIKA
organization_pk = A1
parent_organization_pk = K1

```
↓
```

ZILLA
organization_pk = Z1
parent_organization_pk = A1

```
↓
```

SAKHA
organization_pk = S1
parent_organization_pk = Z1

---

# Cardinality Summary

organization_type_master
1 → N organization

organization_status_master
1 → N organization

organization
1 → N child organization

organization
1 → N organization_address

country_master
1 → N organization_address

state_master
1 → N organization_address

district_master
1 → N organization_address

---

# Design Decisions Frozen

Single organization table

Self-referencing hierarchy

No separate Kendra table

No separate Anchalika table

No separate Zilla table

No separate Sakha table

UUID Primary Keys

Business IDs

Audit Standard Compliant

Soft Delete Compliant
