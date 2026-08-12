# NSS ERP Naming Conventions

Version: 1.0

Status: FROZEN

---

# 1. Purpose

This document defines naming standards for:

* Database Objects
* SQL Scripts
* Django Models
* APIs
* UI Components
* Git Branches

All contributors must follow these standards.

---

# 2. General Rules

Use:

* lowercase
* snake_case
* meaningful names

Avoid:

* abbreviations unless officially approved
* spaces
* special characters

Example:

person_contact

family_relationship

membership_status_history

---

# 3. Database Table Naming

Format:

entity_name

Examples:

person

family_group

sangha_sevi

organization

attendance_review

publication

Avoid:

persons

tbl_person

person_master_data

---

# 4. Primary Key Naming

Format:

table_name_pk

Examples:

person_pk

family_group_pk

sangha_sevi_pk

organization_pk

publication_pk

All primary keys shall be UUID.

---

# 5. Business ID Naming

Format:

table_name_id

Examples:

person_id

family_group_id

sangha_sevi_id

organization_id

publication_id

Business IDs are user-visible identifiers.

Business IDs are NOT primary keys.

---

# 6. Foreign Key Naming

Format:

referenced_table_pk

Examples:

person_pk

family_group_pk

organization_pk

membership_type_pk

Always reference UUID primary keys.

Never reference business IDs.

---

# 7. Audit Column Naming

Mandatory standard:

created_at

created_by_sangha_sevi_pk

updated_at

updated_by_sangha_sevi_pk

deleted_at

deleted_by_sangha_sevi_pk

is_active

---

# 8. Master Table Naming

Format:

entity_master

Examples:

membership_type_master

membership_status_master

organization_type_master

position_master

country_master

state_master

district_master

---

# 9. History Table Naming

Format:

entity_history

Examples:

membership_status_history

family_head_history

position_assignment_history

---

# 10. Junction Table Naming

Format:

relationship_name

Examples:

family_relationship

body_member_assignment

role_permission

user_role

Avoid generic names like:

mapping_table

link_table

xref_table

---

# 11. Index Naming

Format:

idx_table_column

Examples:

idx_person_mobile_no

idx_sangha_sevi_id

idx_family_group_id

---

# 12. Unique Constraint Naming

Format:

uk_table_column

Examples:

uk_person_id

uk_sangha_sevi_id

uk_family_group_id

---

# 13. Foreign Key Constraint Naming

Format:

fk_child_parent

Examples:

fk_sangha_sevi_person

fk_family_relationship_person

fk_family_relationship_family_group

---

# 14. Check Constraint Naming

Format:

chk_table_rule

Examples:

chk_person_gender

chk_membership_status

chk_pranami_amount

---

# 15. Sequence Naming

Format:

seq_entity

Examples:

seq_person

seq_family_group

seq_sangha_sevi

---

# 16. SQL File Naming

Format:

NN_description.sql

Examples:

01_person.sql

02_person_contact.sql

03_person_identity_document.sql

Use leading numbers to preserve execution order.

---

# 17. Django Model Naming

Format:

PascalCase

Examples:

Person

FamilyGroup

SanghaSevi

MembershipStatusHistory

---

# 18. API Naming

Format:

kebab-case

Examples:

/api/persons

/api/families

/api/memberships

/api/attendance-reviews

---

# 19. Git Branch Naming

Format:

feature/module-name

Examples:

feature/foundation-schema

feature/person-module

feature/family-module

feature/membership-module

feature/governance-module

fix/attendance-review

hotfix/login-issue

---

# 20. Naming Principles

Consistency over creativity.

Prefer clarity over brevity.

Names must remain understandable after 10 years.

Database naming standards take precedence over developer preference.
